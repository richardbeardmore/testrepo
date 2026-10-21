"""RFB (VNC) client protocol engine used by the DPR Remote Viewer.

Speaks RFB 3.3/3.7/3.8 with no authentication or VNC password authentication,
and decodes Raw, CopyRect, RRE, Hextile and ZRLE rectangles plus the
DesktopSize and LastRect pseudo-encodings. The framebuffer is a numpy array
of shape (height, width, 4) holding B, G, R, X bytes.

Network I/O runs on a background thread; callbacks are invoked from that
thread, so GUI code must marshal them onto its own thread.
"""

import logging
import socket
import struct
import threading
import zlib

import numpy as np

from . import rfb
from .des import vnc_auth_response

log = logging.getLogger(__name__)

# 32bpp little-endian 0x00RRGGBB: memory order is B, G, R, X.
CLIENT_FORMAT = rfb.PixelFormat()

ENCODINGS = [
    rfb.ENC_ZRLE, rfb.ENC_HEXTILE, rfb.ENC_RRE, rfb.ENC_COPYRECT, rfb.ENC_RAW,
    rfb.ENC_DESKTOP_SIZE, rfb.ENC_LAST_RECT,
]


class _Reader:
    """Exact-length reads over a buffered socket file or any binary stream."""

    def __init__(self, stream):
        self.stream = stream

    def read(self, n):
        data = self.stream.read(n)
        if data is None or len(data) != n:
            raise rfb.ProtocolError("connection closed by server")
        return data

    def u8(self):
        return self.read(1)[0]

    def u16(self):
        return struct.unpack(">H", self.read(2))[0]

    def u32(self):
        return struct.unpack(">I", self.read(4))[0]


# --------------------------------------------------------------------------
# Rectangle decoders. Each writes into fb (h, w, 4 uint8 BGRX) in place.
# --------------------------------------------------------------------------

def _pixels(data, count):
    return np.frombuffer(data, np.uint8).reshape(count, 4)


def decode_raw(r, fb, x, y, w, h):
    fb[y:y + h, x:x + w] = np.frombuffer(r.read(w * h * 4), np.uint8).reshape(h, w, 4)


def decode_copyrect(r, fb, x, y, w, h):
    sx, sy = struct.unpack(">HH", r.read(4))
    fb[y:y + h, x:x + w] = fb[sy:sy + h, sx:sx + w].copy()


def decode_rre(r, fb, x, y, w, h):
    count = r.u32()
    fb[y:y + h, x:x + w] = _pixels(r.read(4), 1)[0]
    if count:
        data = r.read(count * 12)
        for i in range(count):
            off = i * 12
            px = np.frombuffer(data, np.uint8, 4, off)
            sx, sy, sw, sh = struct.unpack_from(">HHHH", data, off + 4)
            fb[y + sy:y + sy + sh, x + sx:x + sx + sw] = px


def decode_hextile(r, fb, x, y, w, h):
    bg = np.zeros(4, np.uint8)
    fg = np.zeros(4, np.uint8)
    for ty in range(y, y + h, 16):
        th = min(16, y + h - ty)
        for tx in range(x, x + w, 16):
            tw = min(16, x + w - tx)
            sub = r.u8()
            tile = fb[ty:ty + th, tx:tx + tw]
            if sub & 1:  # Raw
                tile[:] = np.frombuffer(r.read(tw * th * 4), np.uint8).reshape(th, tw, 4)
                continue
            if sub & 2:
                bg = np.frombuffer(r.read(4), np.uint8)
            tile[:] = bg
            if sub & 4:
                fg = np.frombuffer(r.read(4), np.uint8)
            if sub & 8:
                n = r.u8()
                coloured = sub & 16
                size = 6 if coloured else 2
                data = r.read(n * size)
                for i in range(n):
                    off = i * size
                    if coloured:
                        colour = np.frombuffer(data, np.uint8, 4, off)
                        off += 4
                    else:
                        colour = fg
                    xy, wh = data[off], data[off + 1]
                    sx, sy = xy >> 4, xy & 15
                    sw, sh = (wh >> 4) + 1, (wh & 15) + 1
                    tile[sy:sy + sh, sx:sx + sw] = colour


class ZRLEDecoder:
    """ZRLE decoding with the per-connection zlib stream ZRLE requires."""

    def __init__(self):
        self.z = zlib.decompressobj()

    def decode(self, r, fb, x, y, w, h):
        data = self.z.decompress(r.read(r.u32()))
        view = memoryview(data)
        pos = 0

        def cpixels(n):
            # CPIXEL for our format is 3 bytes: B, G, R.
            nonlocal pos
            arr = np.frombuffer(view[pos:pos + n * 3], np.uint8).reshape(n, 3)
            pos += n * 3
            out = np.zeros((n, 4), np.uint8)
            out[:, :3] = arr
            return out

        def run_length():
            nonlocal pos
            length = 1
            while True:
                b = data[pos]
                pos += 1
                length += b
                if b != 255:
                    return length

        for ty in range(y, y + h, 64):
            th = min(64, y + h - ty)
            for tx in range(x, x + w, 64):
                tw = min(64, x + w - tx)
                n = tw * th
                sub = data[pos]
                pos += 1
                tile = fb[ty:ty + th, tx:tx + tw]
                if sub == 0:
                    tile[:] = cpixels(n).reshape(th, tw, 4)
                elif sub == 1:
                    tile[:] = cpixels(1)[0]
                elif 2 <= sub <= 16:
                    palette = cpixels(sub)
                    bits = 1 if sub == 2 else 2 if sub <= 4 else 4
                    row_bytes = (tw * bits + 7) // 8
                    packed = np.frombuffer(view[pos:pos + row_bytes * th], np.uint8).reshape(th, row_bytes)
                    pos += row_bytes * th
                    unpacked = np.unpackbits(packed, axis=1).reshape(th, row_bytes * 8 // bits, bits)
                    weights = (1 << np.arange(bits - 1, -1, -1)).astype(np.uint8)
                    idx = (unpacked * weights).sum(axis=2)[:, :tw]
                    tile[:] = palette[idx]
                elif sub == 128:
                    out = np.empty((n, 4), np.uint8)
                    filled = 0
                    while filled < n:
                        px = cpixels(1)[0]
                        length = run_length()
                        out[filled:filled + length] = px
                        filled += length
                    tile[:] = out[:n].reshape(th, tw, 4)
                elif sub >= 130:
                    palette = cpixels(sub - 128)
                    out = np.empty((n, 4), np.uint8)
                    filled = 0
                    while filled < n:
                        b = data[pos]
                        pos += 1
                        length = run_length() if b & 128 else 1
                        out[filled:filled + length] = palette[b & 127]
                        filled += length
                    tile[:] = out[:n].reshape(th, tw, 4)
                else:
                    raise rfb.ProtocolError(f"invalid ZRLE subencoding {sub}")


# --------------------------------------------------------------------------
# Connection
# --------------------------------------------------------------------------

class VNCClient:
    """One connection to a VNC server.

    Callbacks (all optional, called on the network thread):
      on_update(x, y, w, h)  bounding box of a completed framebuffer update
      on_resize(w, h)        remote desktop size changed
      on_cut_text(text)      server clipboard text
      on_bell()
      on_disconnect(error)   error is None for a clean local disconnect
    """

    def __init__(self, host, port=5900, password=None, shared=True, timeout=10, encodings=None):
        self.host, self.port = host, port
        # Preferred encodings first; pseudo-encodings are always added.
        self.encodings = list(encodings or ENCODINGS)
        for pseudo in (rfb.ENC_DESKTOP_SIZE, rfb.ENC_LAST_RECT):
            if pseudo not in self.encodings:
                self.encodings.append(pseudo)
        self.password = password
        self.shared = shared
        self.timeout = timeout
        self.sock = None
        self.width = self.height = 0
        self.name = ""
        self.server_version = None
        self.fb = None
        self.fb_lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.encoding_counts = {}
        self.on_update = self.on_resize = self.on_cut_text = None
        self.on_bell = self.on_disconnect = None
        self._closing = False
        self._thread = None

    # ---- handshake -------------------------------------------------------

    def connect(self):
        """Connect and complete the handshake. Raises ProtocolError/OSError on failure."""
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            self._reader = _Reader(self.sock.makefile("rb"))
            self._handshake()
        except Exception:
            self.sock.close()
            raise
        self.sock.settimeout(None)

    def _handshake(self):
        r = self._reader
        server_version = r.read(12)
        if not server_version.startswith(b"RFB "):
            raise rfb.ProtocolError("not a VNC server")
        minor = rfb.parse_version(server_version)
        self.server_version = server_version.decode("ascii", "replace").strip()
        self._send(b"RFB 003.%03d\n" % minor)

        if minor == 3:
            sec = r.u32()
            if sec == rfb.SEC_INVALID:
                raise rfb.ProtocolError(self._reason())
            types = [sec]
        else:
            count = r.u8()
            if count == 0:
                raise rfb.ProtocolError(self._reason())
            types = list(r.read(count))

        if rfb.SEC_VNC_AUTH in types:
            chosen = rfb.SEC_VNC_AUTH
        elif rfb.SEC_NONE in types:
            chosen = rfb.SEC_NONE
        else:
            names = ", ".join(rfb.SECURITY_NAMES.get(t, f"type {t}") for t in types)
            raise rfb.ProtocolError(
                f"The server only offers security types this viewer does not support ({names}). "
                "On RealVNC Server set Encryption to 'Prefer off' or 'Always off' and "
                "Authentication to 'VNC password'.")
        if minor != 3:
            self._send(bytes([chosen]))

        if chosen == rfb.SEC_VNC_AUTH:
            if not self.password:
                raise rfb.AuthenticationError("This server requires a password.")
            challenge = r.read(16)
            self._send(vnc_auth_response(self.password, challenge))
        if chosen == rfb.SEC_VNC_AUTH or minor == 8:
            if r.u32() != 0:
                reason = self._reason() if minor == 8 else "Authentication failed."
                raise rfb.AuthenticationError(reason or "Authentication failed.")

        self._send(bytes([1 if self.shared else 0]))
        self.width, self.height = r.u16(), r.u16()
        r.read(16)  # server's native pixel format; we request our own below
        self.name = r.read(r.u32()).decode("utf-8", "replace")
        self.fb = np.zeros((self.height, self.width, 4), np.uint8)

        self._send(struct.pack(">B3x", rfb.MSG_SET_PIXEL_FORMAT) + CLIENT_FORMAT.pack())
        self._send(struct.pack(">BxH", rfb.MSG_SET_ENCODINGS, len(self.encodings))
                   + struct.pack(f">{len(self.encodings)}i", *self.encodings))
        self._zrle = ZRLEDecoder()
        self.request_update(incremental=False)

    def _reason(self):
        r = self._reader
        try:
            return r.read(r.u32()).decode("utf-8", "replace")
        except rfb.ProtocolError:
            return "Connection refused by server."

    # ---- message loop ----------------------------------------------------

    def start(self):
        self._thread = threading.Thread(target=self._run, name="vnc-client", daemon=True)
        self._thread.start()

    def _run(self):
        error = None
        try:
            while True:
                self._handle_message()
        except Exception as exc:
            if not self._closing:
                log.debug("connection ended", exc_info=True)
                error = str(exc) or exc.__class__.__name__
        finally:
            try:
                self.sock.close()
            except OSError:
                pass
            if self.on_disconnect:
                self.on_disconnect(error)

    def _handle_message(self):
        r = self._reader
        kind = r.u8()
        if kind == rfb.MSG_FB_UPDATE:
            self._framebuffer_update()
        elif kind == rfb.MSG_SET_COLOUR_MAP:
            r.read(3)
            r.read(r.u16() * 6)
        elif kind == rfb.MSG_BELL:
            if self.on_bell:
                self.on_bell()
        elif kind == rfb.MSG_SERVER_CUT_TEXT:
            r.read(3)
            length = struct.unpack(">i", r.read(4))[0]
            data = r.read(abs(length))
            if length >= 0 and self.on_cut_text:
                self.on_cut_text(data.decode("latin-1"))
        else:
            raise rfb.ProtocolError(f"unknown server message type {kind}")

    def _framebuffer_update(self):
        r = self._reader
        r.read(1)
        count = r.u16()
        box = None
        resized = None
        for _ in range(count):
            x, y, w, h, enc = struct.unpack(">HHHHi", r.read(12))
            if enc == rfb.ENC_LAST_RECT:
                break
            if enc == rfb.ENC_DESKTOP_SIZE:
                with self.fb_lock:
                    self.width, self.height = w, h
                    self.fb = np.zeros((h, w, 4), np.uint8)
                resized = (w, h)
                box = (0, 0, w, h)
                continue
            if x + w > self.width or y + h > self.height:
                raise rfb.ProtocolError("rectangle outside framebuffer")
            with self.fb_lock:
                if enc == rfb.ENC_RAW:
                    decode_raw(r, self.fb, x, y, w, h)
                elif enc == rfb.ENC_COPYRECT:
                    decode_copyrect(r, self.fb, x, y, w, h)
                elif enc == rfb.ENC_RRE:
                    decode_rre(r, self.fb, x, y, w, h)
                elif enc == rfb.ENC_HEXTILE:
                    decode_hextile(r, self.fb, x, y, w, h)
                elif enc == rfb.ENC_ZRLE:
                    self._zrle.decode(r, self.fb, x, y, w, h)
                else:
                    raise rfb.ProtocolError(f"server used unrequested encoding {enc}")
            self.encoding_counts[enc] = self.encoding_counts.get(enc, 0) + 1
            box = _union(box, (x, y, w, h))
        if resized and self.on_resize:
            self.on_resize(*resized)
        if box and self.on_update:
            self.on_update(*box)
        self.request_update(incremental=True)

    # ---- client -> server ------------------------------------------------

    def _send(self, data):
        with self.send_lock:
            self.sock.sendall(data)

    def request_update(self, incremental=True):
        self._send(struct.pack(">BBHHHH", rfb.MSG_FB_UPDATE_REQUEST, int(incremental),
                               0, 0, self.width, self.height))

    def key_event(self, keysym, down):
        self._send(struct.pack(">BBxxI", rfb.MSG_KEY_EVENT, int(down), keysym))

    def pointer_event(self, x, y, buttons):
        x = max(0, min(self.width - 1, int(x)))
        y = max(0, min(self.height - 1, int(y)))
        self._send(struct.pack(">BBHH", rfb.MSG_POINTER_EVENT, buttons & 0xFF, x, y))

    def cut_text(self, text):
        data = text.encode("latin-1", "replace")
        self._send(struct.pack(">B3xI", rfb.MSG_CLIENT_CUT_TEXT, len(data)) + data)

    def send_ctrl_alt_del(self):
        for k in (rfb.XK_CONTROL_L, rfb.XK_ALT_L, rfb.XK_DELETE):
            self.key_event(k, True)
        for k in (rfb.XK_DELETE, rfb.XK_ALT_L, rfb.XK_CONTROL_L):
            self.key_event(k, False)

    def snapshot(self):
        """A copy of the framebuffer, safe to use from another thread."""
        with self.fb_lock:
            return self.fb.copy()

    def close(self):
        self._closing = True
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()


def _union(a, b):
    if a is None:
        return b
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1 = max(a[0] + a[2], b[0] + b[2])
    y1 = max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)

"""Shared RFB (VNC) protocol definitions and helpers (RFC 6143)."""

import struct
from dataclasses import dataclass

import numpy as np

# Security types
SEC_INVALID = 0
SEC_NONE = 1
SEC_VNC_AUTH = 2

# Client -> server messages
MSG_SET_PIXEL_FORMAT = 0
MSG_SET_ENCODINGS = 2
MSG_FB_UPDATE_REQUEST = 3
MSG_KEY_EVENT = 4
MSG_POINTER_EVENT = 5
MSG_CLIENT_CUT_TEXT = 6

# Server -> client messages
MSG_FB_UPDATE = 0
MSG_SET_COLOUR_MAP = 1
MSG_BELL = 2
MSG_SERVER_CUT_TEXT = 3

# Encodings
ENC_RAW = 0
ENC_COPYRECT = 1
ENC_RRE = 2
ENC_HEXTILE = 5
ENC_ZRLE = 16
ENC_CURSOR = -239
ENC_DESKTOP_SIZE = -223
ENC_LAST_RECT = -224

ENCODING_NAMES = {
    ENC_RAW: "Raw",
    ENC_COPYRECT: "CopyRect",
    ENC_RRE: "RRE",
    ENC_HEXTILE: "Hextile",
    ENC_ZRLE: "ZRLE",
}

# Protocol versions as (major, minor)
VERSIONS = {b"RFB 003.003\n": 3, b"RFB 003.007\n": 7, b"RFB 003.008\n": 8}

# Keysyms for Ctrl+Alt+Del
XK_CONTROL_L = 0xFFE3
XK_ALT_L = 0xFFE9
XK_DELETE = 0xFFFF


class ProtocolError(Exception):
    """Raised when the peer violates the RFB protocol or closes the connection."""


class AuthenticationError(ProtocolError):
    """Raised when VNC authentication fails."""


def recv_exact(sock, n):
    """Read exactly n bytes from a socket or raise ProtocolError."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ProtocolError("connection closed by peer")
        buf += chunk
    return bytes(buf)


def parse_version(data):
    """Return the minor version (3, 7 or 8) for a ProtocolVersion message.

    Unknown versions are handled as the spec recommends: anything between 3.3
    and 3.8 that is not 3.7/3.8 is treated as 3.3, anything newer as 3.8.
    """
    if data in VERSIONS:
        return VERSIONS[data]
    try:
        major, minor = int(data[4:7]), int(data[8:11])
    except ValueError:
        raise ProtocolError(f"bad protocol version {data!r}")
    if major != 3:
        return 8 if major > 3 else 3
    return 8 if minor >= 8 else (7 if minor == 7 else 3)


@dataclass
class PixelFormat:
    bpp: int = 32
    depth: int = 24
    big_endian: bool = False
    true_colour: bool = True
    red_max: int = 255
    green_max: int = 255
    blue_max: int = 255
    red_shift: int = 16
    green_shift: int = 8
    blue_shift: int = 0

    STRUCT = struct.Struct(">BBBBHHHBBB3x")

    def pack(self):
        return self.STRUCT.pack(
            self.bpp, self.depth, int(self.big_endian), int(self.true_colour),
            self.red_max, self.green_max, self.blue_max,
            self.red_shift, self.green_shift, self.blue_shift,
        )

    @classmethod
    def unpack(cls, data):
        f = cls.STRUCT.unpack(data)
        return cls(f[0], f[1], bool(f[2]), bool(f[3]), *f[4:])

    @property
    def bytes_per_pixel(self):
        return self.bpp // 8

    @property
    def dtype(self):
        base = {8: "u1", 16: "u2", 32: "u4"}[self.bpp]
        return np.dtype((">" if self.big_endian else "<") + base)

    def cpixel_slice(self):
        """Byte slice of a pixel that forms a ZRLE CPIXEL (RFC 6143 7.7.6).

        CPIXELs are 3 bytes when the format is 32bpp true colour of depth
        <= 24 and all colour bits fit in the 3 least (or most) significant
        bytes; otherwise they are the full pixel.
        """
        if self.bpp == 32 and self.true_colour and self.depth <= 24:
            mask = ((self.red_max << self.red_shift) | (self.green_max << self.green_shift)
                    | (self.blue_max << self.blue_shift))
            if mask < 1 << 24:  # fits in least significant bytes
                return slice(0, 3) if not self.big_endian else slice(1, 4)
            if mask & 0xFF == 0:  # fits in most significant bytes
                return slice(1, 4) if not self.big_endian else slice(0, 3)
        return slice(0, self.bytes_per_pixel)

    def from_rgb(self, rgb):
        """Convert an (h, w, 3) uint8 RGB array into packed pixel bytes (h, w) array."""
        r = rgb[..., 0].astype(np.uint32)
        g = rgb[..., 1].astype(np.uint32)
        b = rgb[..., 2].astype(np.uint32)
        if self.true_colour:
            v = ((r * self.red_max + 127) // 255) << self.red_shift
            v |= ((g * self.green_max + 127) // 255) << self.green_shift
            v |= ((b * self.blue_max + 127) // 255) << self.blue_shift
        else:
            # Colour-map formats use the fixed BGR233 map sent by the server.
            v = (r >> 5) | ((g >> 5) << 3) | ((b >> 6) << 6)
        return v.astype(self.dtype)

    def to_rgb(self, pixels):
        """Convert an array of pixel values (any shape) into uint8 RGB (shape + (3,))."""
        v = pixels.astype(np.uint32)
        out = np.empty(pixels.shape + (3,), np.uint8)
        for i, (mx, sh) in enumerate(((self.red_max, self.red_shift),
                                      (self.green_max, self.green_shift),
                                      (self.blue_max, self.blue_shift))):
            out[..., i] = ((v >> sh) & mx) * 255 // max(mx, 1)
        return out


def bgr233_colour_map():
    """Colour map entries (r, g, b as 16-bit) matching PixelFormat.from_rgb for colour-map clients."""
    entries = []
    for i in range(256):
        r, g, b = i & 7, (i >> 3) & 7, (i >> 6) & 3
        entries.append((r * 65535 // 7, g * 65535 // 7, b * 65535 // 3))
    return entries


def parse_display(target, default_port=5900):
    """Parse 'host', 'host:display', 'host::port' or '[ipv6]:display' into (host, port)."""
    target = target.strip()
    if "::" in target and not target.startswith("["):
        host, port = target.rsplit("::", 1)
        return host or "localhost", int(port)
    if target.startswith("["):
        host, _, rest = target[1:].partition("]")
        if rest.startswith("::"):
            return host, int(rest[2:])
        if rest.startswith(":"):
            return host, _display_to_port(int(rest[1:]), default_port)
        return host, default_port
    if target.count(":") == 1:
        host, disp = target.split(":")
        return host or "localhost", _display_to_port(int(disp), default_port)
    return target or "localhost", default_port


def _display_to_port(n, default_port):
    # Values below 100 are display numbers; anything larger is a literal port.
    return default_port + n if n < 100 else n

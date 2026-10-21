"""DPR Controls Ltd brand assets shared by the viewer and the server.

Colours match the DPR Controls website (website/index.html).
"""

import time
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

COMPANY = "DPR Controls Ltd"
SHORT_NAME = "DPR Controls"
TAGLINE = "Control & Automation Engineers"
LOCATION = "Congleton, Cheshire"
PRODUCT = "DPR Remote"
VIEWER_TITLE = "DPR Remote Viewer"
SERVER_TITLE = "DPR Remote Server"

NAVY = "#0d1b2a"
NAVY_2 = "#13263a"
STEEL = "#1b3a5b"
INK = "#22303f"
BODY = "#46586b"
LINE = "#dde5ec"
BG_SOFT = "#f4f7fa"
WHITE = "#ffffff"
MUTED = "#9fb3c8"
LIGHT = "#c9d6e2"
ACCENT = "#f59e0b"
ACCENT_DARK = "#d97706"
ACCENT_LIGHT = "#fbbf24"
BLUE = "#2286d3"
OK = "#22a06b"
ERROR = "#e5484d"

# Tk picks the first installed family.
FONT_FAMILIES = ("Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans")


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def font(size, bold=False):
    """A PIL font at the given pixel size, falling back to Pillow's built-in font."""
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf", "segoeuib.ttf"] if bold
             else ["DejaVuSans.ttf", "arial.ttf", "segoeui.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


@lru_cache(maxsize=16)
def logo_mark(size=64):
    """The DPR mark: an amber gradient rounded square with 'DPR' in navy."""
    scale = 4  # supersample for smooth edges
    s = size * scale
    top, bottom = _hex(ACCENT), _hex(ACCENT_DARK)
    grad = Image.new("RGB", (s, s))
    px = grad.load()
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * s)
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.24), fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    f = font(int(s * 0.36), bold=True)
    d.text((s / 2, s / 2), "DPR", font=f, fill=_hex(NAVY), anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def window_icons():
    """PIL images suitable for Tk's iconphoto at several sizes."""
    return [logo_mark(n) for n in (16, 32, 48, 64, 128)]


class DemoPattern:
    """A branded, animated test desktop used by the server's 'demo' source.

    It reacts to pointer and key events so a remote session can be exercised
    without capturing a real screen (useful for demos and automated tests).
    """

    def __init__(self, width=1280, height=720):
        self.width, self.height = width, height
        self.pointer = (width // 2, height // 2)
        self.buttons = 0
        self.marks = []
        self.typed = ""
        self._title_font = font(44, bold=True)
        self._sub_font = font(22)
        self._mono = font(20)
        self._small = font(16)
        self._base = self._render_base()

    def _render_base(self):
        w, h = self.width, self.height
        img = Image.new("RGB", (w, h), _hex(NAVY))
        d = ImageDraw.Draw(img)
        # subtle steel gradient band
        for y in range(h):
            t = y / h
            c = tuple(int(a + (b - a) * t) for a, b in zip(_hex(NAVY), _hex(STEEL)))
            d.line([(0, y), (w, y)], fill=c)
        img.paste(logo_mark(96), (48, 40), logo_mark(96))
        d.text((168, 52), SHORT_NAME, font=self._title_font, fill=_hex(WHITE))
        d.text((170, 106), TAGLINE.upper(), font=self._small, fill=_hex(MUTED))
        d.text((48, 170), f"{PRODUCT} demo desktop", font=self._sub_font, fill=_hex(LIGHT))
        # colour bars for checking pixel formats
        bars = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0),
                (255, 0, 255), (255, 0, 0), (0, 0, 255), _hex(ACCENT)]
        bw = (w - 96) // len(bars)
        for i, c in enumerate(bars):
            d.rectangle((48 + i * bw, 220, 48 + (i + 1) * bw - 1, 290), fill=c)
        # input console box
        d.rounded_rectangle((48, 330, w - 48, 420), radius=10, fill=_hex(NAVY_2), outline=_hex(STEEL))
        d.text((64, 340), "Keyboard input", font=self._small, fill=_hex(MUTED))
        d.text((48, h - 40), f"{COMPANY}  ·  {LOCATION}", font=self._small, fill=_hex(MUTED))
        return img

    def handle_pointer(self, x, y, mask):
        self.pointer = (x, y)
        if mask & 1 and not self.buttons & 1:
            self.marks = (self.marks + [(x, y)])[-50:]
        self.buttons = mask

    def handle_key(self, keysym, down):
        if not down:
            return
        if keysym == 0xFF08:  # BackSpace
            self.typed = self.typed[:-1]
        elif keysym in (0xFF0D, 0xFF8D):  # Return
            self.typed = ""
        elif 0x20 <= keysym <= 0xFF:
            self.typed = (self.typed + chr(keysym))[-80:]
        elif keysym & 0xFF000000 == 0x01000000:
            self.typed = (self.typed + chr(keysym & 0xFFFFFF))[-80:]

    def render(self, now):
        img = self._base.copy()
        d = ImageDraw.Draw(img)
        w = self.width
        # animated progress bar
        span = w - 96
        pos = int((now * 0.25 % 1.0) * span)
        d.rectangle((48, 300, 48 + span, 308), fill=_hex(NAVY_2))
        d.rectangle((48, 300, 48 + pos, 308), fill=_hex(ACCENT))
        d.text((w - 48, 60), time.strftime("%H:%M:%S", time.localtime(now)),
               font=self._title_font, fill=_hex(ACCENT), anchor="ra")
        d.text((w - 48, 112), time.strftime("%A %d %B %Y", time.localtime(now)),
               font=self._small, fill=_hex(MUTED), anchor="ra")
        d.text((64, 370), self.typed + "_", font=self._mono, fill=_hex(WHITE))
        for mx, my in self.marks:
            d.ellipse((mx - 6, my - 6, mx + 6, my + 6), fill=_hex(BLUE), outline=_hex(WHITE))
        return img

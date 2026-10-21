"""DPR Controls Ltd brand assets used to rebrand the viewer.

Colours match the DPR Controls website (website/index.html).
"""

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

COMPANY = "DPR Controls Ltd"
SHORT_NAME = "DPR Controls"
TAGLINE = "Control & Automation Engineers"
LOCATION = "Congleton, Cheshire"
PRODUCT = "DPR Remote Viewer"

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

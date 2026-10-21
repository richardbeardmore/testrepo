#!/usr/bin/env python3
"""Apply DPR Controls branding to a TigerVNC source tree.

Usage:
    python3 rebrand.py path/to/tigervnc [--source-url URL]

The script edits the tree in place: product names in user-visible strings,
the About box, window titles, installer/package metadata and the icons.
TigerVNC's copyright notices and GPL licence are kept, as the licence
requires. Every replacement must match the expected number of times (once unless noted), so a TigerVNC release
that changes these strings fails loudly instead of being half-branded.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

import branding as b

SUPPORTED_TAG = "v1.15.0"
DEFAULT_SOURCE_URL = "https://github.com/richardbeardmore/testrepo"

NAME = b.PRODUCT            # "DPR Remote Viewer"
COMPANY = b.COMPANY         # "DPR Controls Ltd"


# Navy header with the DPR mark at the top of the connection dialog.
SERVER_DIALOG_HEADER = f"""\
  // DPR Controls branded header
  Fl_Box *header = new Fl_Box(0, 0, w(), 64);
  header->box(FL_FLAT_BOX);
  header->color(fl_rgb_color(0x0d, 0x1b, 0x2a));

  Fl_Box *logo = new Fl_Box(OUTER_MARGIN, 12, 40, 40);
  logo->image(new Fl_PNG_Image(nullptr, dpr_logo_png, sizeof(dpr_logo_png)));

  Fl_Box *title = new Fl_Box(OUTER_MARGIN + 52, 12, w() - OUTER_MARGIN*2 - 52, 22, "{NAME}");
  title->align(FL_ALIGN_LEFT | FL_ALIGN_INSIDE);
  title->labelcolor(FL_WHITE);
  title->labelfont(FL_HELVETICA_BOLD);
  title->labelsize(16);

  Fl_Box *tagline = new Fl_Box(OUTER_MARGIN + 52, 34, w() - OUTER_MARGIN*2 - 52, 18,
                               "{COMPANY}  \u00b7  {b.TAGLINE}");
  tagline->align(FL_ALIGN_LEFT | FL_ALIGN_INSIDE);
  tagline->labelcolor(fl_rgb_color(0x9f, 0xb3, 0xc8));
  tagline->labelsize(11);

  x = OUTER_MARGIN;
  y = header->h() + OUTER_MARGIN;
"""


def replacements(source_url):
    about = (
        f'_("{NAME} v%s (based on TigerVNC)\\n"\n'
        f'             "Built on: %s\\n"\n'
        f'             "{COMPANY}, {b.LOCATION}\\n"\n'
        '             "Copyright (C) 1999-%d TigerVNC team and many others (see README.rst)\\n"\n'
        '             "Licensed under the GNU General Public License v2.\\n"\n'
        f'             "Source code: {source_url}")'
    )
    return {
        "vncviewer/vncviewer.cxx": [
            ('_("TigerVNC viewer v%s\\n"\n'
             '             "Built on: %s\\n"\n'
             '             "Copyright (C) 1999-%d TigerVNC team and many others (see README.rst)\\n"\n'
             '             "See https://www.tigervnc.org for information on TigerVNC.")',
             about),
            ('_("About TigerVNC Viewer")', f'_("About {NAME}")'),
            ('fl_message_title_default(_("TigerVNC viewer"))', f'fl_message_title_default(_("{NAME}"))'),
            ('_("Error starting new TigerVNC Viewer: %s")', f'_("Error starting new {NAME}: %s")', 2),
            ('TigerVNC viewer will now exit.', f'{NAME} will now exit.'),
            # Brand accent for selections and highlighted menu items.
            ('  Fl_Window::default_xclass("vncviewer");\n',
             '  Fl_Window::default_xclass("vncviewer");\n\n'
             '  // DPR Controls brand accent (amber #f59e0b).\n'
             '  Fl::set_color(FL_SELECTION_COLOR, 0xf5, 0x9e, 0x0b);\n'),
        ],
        "vncviewer/ServerDialog.cxx": [
            ('_("VNC viewer: Connection details")', f'_("{NAME}: Connection details")'),
            ('#include <FL/Fl_File_Chooser.H>\n',
             '#include <FL/Fl_File_Chooser.H>\n#include <FL/Fl_PNG_Image.H>\n\n#include "dpr_logo.h"\n'),
            ('  x = OUTER_MARGIN;\n  y = OUTER_MARGIN;\n\n  serverName',
             SERVER_DIALOG_HEADER + '\n  serverName'),
            ('_("Connect"));\n  button->callback(this->handleConnect, this);\n',
             '_("Connect"));\n  button->callback(this->handleConnect, this);\n'
             '  button->color(fl_rgb_color(0xf5, 0x9e, 0x0b));\n'),
        ],
        "vncviewer/DesktopWindow.cxx": [
            ('"%.240s - TigerVNC"', f'"%.240s - {NAME}"'),
        ],
        "vncviewer/OptionsDialog.cxx": [
            ('_("TigerVNC options")', f'_("{NAME} options")'),
        ],
        "vncviewer/Viewport.cxx": [
            ('"About &TigerVNC viewer..."', f'"About &{NAME}..."'),
        ],
        "vncviewer/vncviewer.rc.in": [
            ('"CompanyName", "TigerVNC project\\0"', f'"CompanyName", "{COMPANY}\\0"'),
            ('"FileDescription", "TigerVNC client\\0"', f'"FileDescription", "{NAME} (based on TigerVNC)\\0"'),
            ('"ProductName", "TigerVNC client\\0"', f'"ProductName", "{NAME}\\0"'),
            ('"LegalTrademarks", "TigerVNC\\0"', f'"LegalTrademarks", "{COMPANY}\\0"'),
        ],
        "vncviewer/vncviewer.desktop.in.in": [
            ("Name=TigerVNC viewer", f"Name={NAME}"),
        ],
        "release/tigervnc.iss.in": [
            ("AppName=TigerVNC\n", f"AppName={NAME}\n"),
            ("AppVerName=TigerVNC @VERSION@", f"AppVerName={NAME} @VERSION@"),
            ("AppPublisher=TigerVNC project", f"AppPublisher={COMPANY}"),
            ("AppPublisherURL=https://tigervnc.org", f"AppPublisherURL={source_url}"),
            ("DefaultDirName={pf}\\TigerVNC", f"DefaultDirName={{pf}}\\{NAME}"),
            ("DefaultGroupName=TigerVNC", f"DefaultGroupName={NAME}"),
            ('"{group}\\TigerVNC Viewer"', f'"{{group}}\\{NAME}"'),
            ('"{group}\\Listening TigerVNC Viewer"', f'"{{group}}\\Listening {NAME}"'),
            ('"{group}\\Uninstall TigerVNC"', f'"{{group}}\\Uninstall {NAME}"'),
        ],
        "release/CMakeLists.txt": [
            ("-F${CMAKE_PROJECT_NAME}${INST_SUFFIX}-${VERSION} tigervnc.iss",
             "-FDPR-Remote-Viewer${INST_SUFFIX}-${VERSION} tigervnc.iss"),
        ],
        "release/Info.plist.in": [
            ("<string>TigerVNC viewer</string>\n\t<key>CFBundleExecutable</key>",
             f"<string>{NAME}</string>\n\t<key>CFBundleExecutable</key>"),
            ("<string>com.tigervnc.tigervnc</string>", "<string>uk.co.dprcontrols.remoteviewer</string>"),
            ("<string>TigerVNC viewer @VERSION@</string>", f"<string>{NAME} @VERSION@</string>"),
            ("<key>CFBundleName</key>\n\t<string>TigerVNC viewer</string>",
             f"<key>CFBundleName</key>\n\t<string>{NAME}</string>"),
        ],
    }


# Build fixes for current toolchains, backported from upstream TigerVNC.
# These are not branding; drop each one once a TigerVNC release includes it.
COMPAT_FIXES = {
    # Upstream b752a331: "Don't redefine close() as that easily breaks".
    # Recent MinGW headers declare closesocket() after this macro.
    "common/rdr/FdInStream.cxx": [
        ("#define errorNumber WSAGetLastError()\n#define close closesocket\n",
         "#define errorNumber WSAGetLastError()\n"),
        ("#define errorNumber errno\n#endif",
         "#define errorNumber errno\n#define closesocket close\n#endif"),
        ("if (closeWhenDone) close(fd);", "if (closeWhenDone) closesocket(fd);"),
    ],
}


def apply_replacements(root, source_url):
    edits = {**replacements(source_url)}
    for rel, pairs in COMPAT_FIXES.items():
        edits[rel] = edits.get(rel, []) + pairs
    for rel, pairs in edits.items():
        path = root / rel
        text = path.read_text(encoding="utf-8")
        for old, new, *expected in pairs:
            expected = expected[0] if expected else 1
            count = text.count(old)
            if count != expected:
                sys.exit(f"{rel}: expected {expected} match(es) for {old!r}, found {count}. "
                         f"Is this TigerVNC {SUPPORTED_TAG}?")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        print(f"patched {rel}")


SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{a}"/>
      <stop offset="1" stop-color="{ad}"/>
    </linearGradient>
  </defs>
  <rect width="128" height="128" rx="31" fill="url(#g)"/>
  <text x="64" y="64" dy="0.35em" text-anchor="middle" fill="{n}"
        font-family="Segoe UI, Helvetica, Arial, sans-serif" font-weight="800" font-size="46">DPR</text>
</svg>
"""


def write_icons(root):
    icons = root / "media" / "icons"
    sizes = (16, 22, 24, 32, 48, 64, 128)
    for size in sizes:
        b.logo_mark(size).save(icons / f"tigervnc_{size}.png")
    big = b.logo_mark(256)
    big.save(icons / "tigervnc.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    big.save(icons / "tigervnc.icns")
    svg = SVG.format(a=b.ACCENT, ad=b.ACCENT_DARK, n=b.NAVY, s=128)
    (icons / "tigervnc.svg").write_text(svg)
    media = root / "media"
    (media / "tigervnc.svg").write_text(svg)
    for size in (16, 22, 24, 32, 48):
        (media / f"tigervnc_{size}.svg").write_text(SVG.format(a=b.ACCENT, ad=b.ACCENT_DARK, n=b.NAVY, s=size))
    print("replaced icons")


def write_logo_header(root):
    """Embed the 40px DPR mark as a PNG byte array for the connection dialog."""
    import io
    buf = io.BytesIO()
    b.logo_mark(40).save(buf, "PNG")
    data = buf.getvalue()
    rows = [", ".join(f"0x{c:02x}" for c in data[i:i + 12]) for i in range(0, len(data), 12)]
    body = ",\n  ".join(rows)
    (root / "vncviewer" / "dpr_logo.h").write_text(
        "/* DPR Controls logo mark (generated by dpr-viewer/rebrand.py). */\n"
        "#ifndef DPR_LOGO_H\n#define DPR_LOGO_H\n\n"
        f"static const unsigned char dpr_logo_png[] = {{\n  {body}\n}};\n\n#endif\n")
    print("wrote vncviewer/dpr_logo.h")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tigervnc", type=Path, help="TigerVNC source checkout")
    ap.add_argument("--source-url", default=DEFAULT_SOURCE_URL,
                    help="where recipients can get the source code (shown in the About box)")
    args = ap.parse_args()
    root = args.tigervnc.resolve()
    if not (root / "vncviewer" / "vncviewer.cxx").exists():
        sys.exit(f"{root} does not look like a TigerVNC source tree")
    apply_replacements(root, args.source_url)
    write_icons(root)
    write_logo_header(root)


if __name__ == "__main__":
    main()

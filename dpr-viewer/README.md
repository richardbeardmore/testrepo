# DPR Remote Viewer

A DPR Controls Ltd branded build of the [TigerVNC](https://tigervnc.org) viewer.
It connects to RealVNC, TigerVNC, TightVNC, UltraVNC and x11vnc servers.

Rather than keeping a modified copy of TigerVNC, this folder holds a script
that applies DPR branding to an official TigerVNC release:

| File | Purpose |
| --- | --- |
| `rebrand.py` | Applies the branding to a TigerVNC source checkout |
| `branding.py` | DPR colours, names and the "DPR" logo mark (matches the website) |
| `requirements.txt` | Python dependency (Pillow) for generating the icons |

## What gets rebranded

- Product name "DPR Remote Viewer" in window titles, dialogs, menus and messages
- A navy DPR header with the logo on the connection dialog, and an amber Connect button
- About box: DPR Controls Ltd, plus the TigerVNC copyright, the GPL licence and a link to the source code
- Application icons (Windows `.ico`, macOS `.icns`, Linux PNG/SVG)
- Windows installer: name, publisher, Start-menu entries, install folder, and the
  `DPR-Remote-Viewer64-<version>.exe` file name
- Windows file properties, the macOS bundle name/identifier and the Linux desktop entry

Everything else (protocol, encodings, options, keyboard handling) is unchanged
TigerVNC. Settings and saved connection history are shared with any copy of
TigerVNC on the same machine.

Every replacement in `rebrand.py` must match exactly. If a newer TigerVNC
release changes one of these strings, the script stops with an error instead of
half-branding the tree. Update `SUPPORTED_TAG` and the affected strings when you
move to a new release.

## Building

### Automatically (GitHub Actions)

`.github/workflows/dpr-viewer.yml` runs on every push that touches this folder,
and on demand from the Actions tab. It produces:

- **DPR-Remote-Viewer-Windows**: the Windows installer
- **DPR-Remote-Viewer-Linux**: the Linux binary
- **DPR-Remote-Viewer-source**: the branded source tree (see *Licence* below)

### By hand on Linux

```sh
git clone --depth 1 --branch v1.15.0 https://github.com/TigerVNC/tigervnc.git
pip install -r dpr-viewer/requirements.txt
python3 dpr-viewer/rebrand.py tigervnc

sudo apt-get install cmake g++ libfltk1.3-dev libgnutls28-dev libpixman-1-dev \
  libjpeg-dev zlib1g-dev gettext nettle-dev libgmp-dev libxtst-dev libxrandr-dev \
  libxdamage-dev libxi-dev libxcursor-dev libxinerama-dev libxft-dev libpam0g-dev
cmake -DCMAKE_BUILD_TYPE=Release -S tigervnc -B build
make -C build vncviewer
./build/vncviewer/vncviewer
```

On Windows, use MSYS2 as shown in the workflow. TigerVNC can't be built with
Visual Studio.

## Connecting to RealVNC Server

RealVNC's own encryption and sign-in methods are proprietary, so third-party
viewers (including this one) can't use them. On each RealVNC Server, open
**Options → Security** and set:

- **Encryption:** *Prefer off* (or *Always off*)
- **Authentication:** *VNC password*, and set a VNC password under **Users & Permissions**

Then connect to `host` (display 0, port 5900), `host:1` (display 1) or
`host::port`.

Classic VNC password authentication is weak: passwords are limited to 8
characters, and the session itself is not encrypted. Only use it on a trusted
network, or over a VPN or SSH tunnel, e.g.
`ssh -L 5901:localhost:5900 user@site` and then connect to `localhost:1`. TigerVNC
servers also offer TLS encryption (VeNCrypt), which this viewer supports.

## Licence

TigerVNC is licensed under the GNU General Public License v2. That allows
rebranding, but if you give the viewer to anyone outside DPR Controls (customers,
for example) you must:

1. Keep the TigerVNC copyright notice and licence. The About box and installer
   keep both.
2. Provide the corresponding source code, or a written offer of it. The
   **DPR-Remote-Viewer-source** build artifact is that source. The About box
   links to this repository; pass `--source-url` to `rebrand.py` if the source
   will be published somewhere else.

Don't use the TigerVNC name or logo to promote the product beyond saying it is
based on TigerVNC.

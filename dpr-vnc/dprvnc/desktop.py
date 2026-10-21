"""Desktop sources (screen capture) and input injection for the server."""

import logging
import threading
import time

import numpy as np

from .branding import DemoPattern

log = logging.getLogger(__name__)


class FrameSource:
    """Base class: produces RGB frames and accepts remote input events."""

    name = "source"

    def grab(self):
        """Return the current desktop as an (h, w, 3) uint8 RGB numpy array."""
        raise NotImplementedError

    def pointer_event(self, x, y, mask):
        pass

    def key_event(self, keysym, down):
        pass

    def close(self):
        pass


class DemoSource(FrameSource):
    """An animated branded test desktop that reacts to input; needs no display."""

    name = "demo"

    def __init__(self, width=1280, height=720):
        self.pattern = DemoPattern(width, height)
        self.lock = threading.Lock()

    def grab(self):
        with self.lock:
            return np.asarray(self.pattern.render(time.time()))

    def pointer_event(self, x, y, mask):
        with self.lock:
            self.pattern.handle_pointer(x, y, mask)

    def key_event(self, keysym, down):
        with self.lock:
            self.pattern.handle_key(keysym, down)


class ScreenSource(FrameSource):
    """Captures a real monitor with mss (or Pillow's ImageGrab) and injects input with pynput."""

    name = "screen"

    def __init__(self, monitor=1, view_only=False):
        self._local = threading.local()  # mss handles are not thread-safe
        self._backend = None
        try:
            import mss  # noqa: F401
            self._backend = "mss"
            with self._mss_instance() as probe:
                mons = probe.monitors
            if not 0 <= monitor < len(mons):
                raise ValueError(f"monitor {monitor} not found (have 0..{len(mons) - 1})")
            self.region = dict(mons[monitor])
        except ImportError:
            from PIL import ImageGrab
            self._backend = "imagegrab"
            img = ImageGrab.grab(all_screens=monitor == 0)
            self.region = {"left": 0, "top": 0, "width": img.width, "height": img.height}
        self.injector = None if view_only else InputInjector(self.region)

    @staticmethod
    def _mss_instance():
        import mss
        return mss.mss()

    def grab(self):
        if self._backend == "mss":
            sct = getattr(self._local, "sct", None)
            if sct is None:
                sct = self._local.sct = self._mss_instance()
            shot = sct.grab(self.region)
            # mss returns BGRA
            return np.frombuffer(shot.bgra, np.uint8).reshape(shot.height, shot.width, 4)[..., 2::-1]
        from PIL import ImageGrab
        r = self.region
        box = (r["left"], r["top"], r["left"] + r["width"], r["top"] + r["height"])
        return np.asarray(ImageGrab.grab(bbox=box, all_screens=True).convert("RGB"))

    def pointer_event(self, x, y, mask):
        if self.injector:
            self.injector.pointer(x, y, mask)

    def key_event(self, keysym, down):
        if self.injector:
            self.injector.key(keysym, down)

    def close(self):
        if self.injector:
            self.injector.release_all()


# X11 keysym -> pynput Key attribute name
_SPECIAL_KEYS = {
    0xFF08: "backspace", 0xFF09: "tab", 0xFF0D: "enter", 0xFF13: "pause",
    0xFF14: "scroll_lock", 0xFF1B: "esc", 0xFFFF: "delete", 0xFF50: "home",
    0xFF51: "left", 0xFF52: "up", 0xFF53: "right", 0xFF54: "down",
    0xFF55: "page_up", 0xFF56: "page_down", 0xFF57: "end", 0xFF61: "print_screen",
    0xFF63: "insert", 0xFF67: "menu", 0xFF7F: "num_lock", 0xFF8D: "enter",
    0xFFE1: "shift", 0xFFE2: "shift_r", 0xFFE3: "ctrl", 0xFFE4: "ctrl_r",
    0xFFE5: "caps_lock", 0xFFE7: "cmd", 0xFFE8: "cmd_r", 0xFFE9: "alt",
    0xFFEA: "alt_r", 0xFFEB: "cmd", 0xFFEC: "cmd_r", 0xFE03: "alt_gr",
}
_SPECIAL_KEYS.update({0xFFBE + i: f"f{i + 1}" for i in range(20)})

# Keypad keysyms -> the characters they produce
_KEYPAD_CHARS = {0xFFAA: "*", 0xFFAB: "+", 0xFFAD: "-", 0xFFAE: ".", 0xFFAF: "/", 0xFFBD: "="}
_KEYPAD_CHARS.update({0xFFB0 + i: str(i) for i in range(10)})


class InputInjector:
    """Translates RFB pointer/key events into local input via pynput."""

    def __init__(self, region):
        from pynput import keyboard, mouse
        self._kb_mod, self._mouse_mod = keyboard, mouse
        self.kb = keyboard.Controller()
        self.mouse = mouse.Controller()
        self.region = region
        self.buttons = 0
        self.pressed = {}
        self.lock = threading.Lock()

    def _key_for(self, keysym):
        Key, KeyCode = self._kb_mod.Key, self._kb_mod.KeyCode
        name = _SPECIAL_KEYS.get(keysym)
        if name and hasattr(Key, name):
            return getattr(Key, name)
        if keysym in _KEYPAD_CHARS:
            return KeyCode.from_char(_KEYPAD_CHARS[keysym])
        if 0x20 <= keysym <= 0xFF:
            return KeyCode.from_char(chr(keysym))
        if keysym & 0xFF000000 == 0x01000000:
            return KeyCode.from_char(chr(keysym & 0xFFFFFF))
        return None

    def key(self, keysym, down):
        with self.lock:
            try:
                if down:
                    k = self._key_for(keysym)
                    if k is None:
                        log.debug("unmapped keysym 0x%x", keysym)
                        return
                    self.kb.press(k)
                    self.pressed[keysym] = k
                else:
                    k = self.pressed.pop(keysym, None) or self._key_for(keysym)
                    if k is not None:
                        self.kb.release(k)
            except Exception as exc:  # injection can fail e.g. on secure desktops
                log.warning("key injection failed: %s", exc)

    def pointer(self, x, y, mask):
        Button = self._mouse_mod.Button
        with self.lock:
            try:
                self.mouse.position = (self.region["left"] + x, self.region["top"] + y)
                for bit, btn in ((1, Button.left), (2, Button.middle), (4, Button.right)):
                    if mask & bit and not self.buttons & bit:
                        self.mouse.press(btn)
                    elif self.buttons & bit and not mask & bit:
                        self.mouse.release(btn)
                # wheel "buttons" are sent as press+release pairs; act on press
                pressed = mask & ~self.buttons
                if pressed & 8:
                    self.mouse.scroll(0, 1)
                if pressed & 16:
                    self.mouse.scroll(0, -1)
                if pressed & 32:
                    self.mouse.scroll(-1, 0)
                if pressed & 64:
                    self.mouse.scroll(1, 0)
                self.buttons = mask
            except Exception as exc:
                log.warning("pointer injection failed: %s", exc)

    def release_all(self):
        """Release any keys/buttons a disconnecting client left held down."""
        for keysym in list(self.pressed):
            self.key(keysym, False)
        if self.buttons & 7:
            Button = self._mouse_mod.Button
            for bit, btn in ((1, Button.left), (2, Button.middle), (4, Button.right)):
                if self.buttons & bit:
                    try:
                        self.mouse.release(btn)
                    except Exception:
                        pass
            self.buttons = 0


def open_source(kind="screen", monitor=1, view_only=False, size=(1280, 720)):
    if kind == "demo":
        return DemoSource(*size)
    return ScreenSource(monitor=monitor, view_only=view_only)

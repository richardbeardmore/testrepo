#!/usr/bin/env python3
"""Analog clock with date and digital time display.

Runs on any machine with Python 3.8+ — uses only the standard
library (tkinter), no packages to install.

    python3 analog_clock.py
"""

import math
import tkinter as tk
from datetime import datetime

SIZE = 380                # canvas is square, SIZE x SIZE pixels
CENTER = SIZE / 2
RADIUS = SIZE / 2 - 10
UPDATE_MS = 50            # redraw interval; 50 ms gives a smooth sweep

COLORS = {
    "bg":     "#10151d",
    "face":   "#1b2330",
    "rim":    "#2e3c50",
    "tick":   "#8fa3bd",
    "text":   "#e8eef6",
    "muted":  "#8fa3bd",
    "accent": "#e05252",
}


def hand_angles(now: datetime) -> tuple[float, float, float]:
    """Return (hour, minute, second) hand angles in radians,
    clockwise from 12 o'clock. The hour hand creeps with the
    minutes and the second hand sweeps with the microseconds."""
    second = now.second + now.microsecond / 1_000_000
    minute = now.minute + second / 60
    hour = (now.hour % 12) + minute / 60
    return (
        hour * math.pi / 6,
        minute * math.pi / 30,
        second * math.pi / 30,
    )


def polar(angle: float, radius: float) -> tuple[float, float]:
    """Canvas coordinates of a point at `radius` from the center,
    at `angle` radians clockwise from 12 o'clock."""
    return (
        CENTER + radius * math.sin(angle),
        CENTER - radius * math.cos(angle),
    )


class AnalogClock(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Analog Clock")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        self.canvas = tk.Canvas(
            self, width=SIZE, height=SIZE,
            bg=COLORS["bg"], highlightthickness=0,
        )
        self.canvas.pack(padx=20, pady=(20, 8))

        self.digital = tk.Label(
            self, font=("Consolas", 28, "bold"),
            fg=COLORS["text"], bg=COLORS["bg"],
        )
        self.digital.pack()

        self.date = tk.Label(
            self, font=("Segoe UI", 13),
            fg=COLORS["muted"], bg=COLORS["bg"],
        )
        self.date.pack(pady=(2, 20))

        self._draw_face()

        # Hands and hub are created once, then moved with coords() —
        # cheaper than delete/redraw and it never flickers.
        self.hour_hand = self._make_hand(7, COLORS["text"])
        self.minute_hand = self._make_hand(5, COLORS["text"])
        self.second_hand = self._make_hand(2, COLORS["accent"])
        self.hub = self.canvas.create_oval(
            CENTER - 7, CENTER - 7, CENTER + 7, CENTER + 7,
            fill=COLORS["accent"], outline="",
        )

        self._tick()

    def _draw_face(self) -> None:
        c = self.canvas
        c.create_oval(
            CENTER - RADIUS, CENTER - RADIUS,
            CENTER + RADIUS, CENTER + RADIUS,
            fill=COLORS["face"], outline=COLORS["rim"], width=6,
        )
        for i in range(60):
            angle = i * math.pi / 30
            is_hour = i % 5 == 0
            inner = RADIUS - (22 if is_hour else 12)
            c.create_line(
                *polar(angle, inner), *polar(angle, RADIUS - 6),
                fill=COLORS["tick"], width=4 if is_hour else 1.5,
            )
        for n in range(1, 13):
            c.create_text(
                *polar(n * math.pi / 6, RADIUS - 42),
                text=str(n), fill=COLORS["text"],
                font=("Segoe UI", int(SIZE * 0.055), "bold"),
            )

    def _make_hand(self, width: int, color: str) -> int:
        return self.canvas.create_line(
            CENTER, CENTER, CENTER, CENTER,
            width=width, fill=color, capstyle=tk.ROUND,
        )

    def _tick(self) -> None:
        now = datetime.now()
        hour_a, minute_a, second_a = hand_angles(now)

        for hand, angle, length, tail in (
            (self.hour_hand, hour_a, RADIUS * 0.50, 12),
            (self.minute_hand, minute_a, RADIUS * 0.72, 12),
            (self.second_hand, second_a, RADIUS * 0.80, 20),
        ):
            # each hand runs from a short tail behind the pivot to its tip
            self.canvas.coords(hand, *polar(angle + math.pi, tail),
                               *polar(angle, length))
        self.canvas.tag_raise(self.hub)

        self.digital.config(text=now.strftime("%H:%M:%S"))
        self.date.config(text=now.strftime("%A, %d %B %Y"))

        self.after(UPDATE_MS, self._tick)


if __name__ == "__main__":
    AnalogClock().mainloop()

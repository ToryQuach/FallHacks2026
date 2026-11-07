"""Track the mouse cursor position and buttons in a background thread.

Works on Windows with no third-party dependencies (Win32 ``GetCursorPos``).
On other platforms it falls back to ``pynput`` if that package is installed.

Examples
--------
Print the live cursor position::

    py src/input/mouse_tracker.py

Record the cursor trail to a JSONL file for 10 seconds::

    py src/input/mouse_tracker.py --log trail.jsonl --duration 10

Draw the recent cursor trail in a full-screen overlay (Esc closes it)::

    py src/input/mouse_tracker.py --overlay

Use it from other code::

    from mouse_tracker import MouseTracker

    with MouseTracker(hz=30, log_path="trail.jsonl") as tracker:
        while True:
            print(tracker.position, tracker.buttons)
            time.sleep(1)
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Deque

IS_WINDOWS = sys.platform == "win32"

DEFAULT_HZ = 60.0
DEFAULT_HISTORY = 600

# GetSystemMetrics indices for the virtual desktop (all monitors).
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


@dataclass(frozen=True)
class MouseSample:
    """A single cursor observation.

    Attributes:
        x: Cursor x coordinate in virtual-screen pixels.
        y: Cursor y coordinate in virtual-screen pixels.
        t: Seconds elapsed since the tracker started.
        buttons: Names of the buttons held down at the time of the sample.
    """

    x: int
    y: int
    t: float
    buttons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClickEvent:
    """A button press or release."""

    x: int
    y: int
    t: float
    button: str
    pressed: bool


def screen_rect() -> tuple[int, int, int, int]:
    """Return ``(left, top, width, height)`` of the virtual desktop.

    Coordinates can be negative when a monitor is left of / above the primary
    screen, so use this to convert absolute cursor positions to overlay
    coordinates.
    """
    if IS_WINDOWS:
        user32 = ctypes.windll.user32
        return (
            user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )

    try:
        import tkinter as tk
    except ImportError as error:  # pragma: no cover - depends on platform
        raise RuntimeError("cannot determine screen size without tkinter") from error

    root = tk._default_root or tk.Tk()
    root.withdraw()
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class _WindowsBackend:
    """Cursor and button state via the Win32 API."""

    _VK_BUTTONS = {"left": 0x01, "right": 0x02, "middle": 0x04}

    def __init__(self) -> None:
        from ctypes import wintypes

        self._wintypes = wintypes
        self._user32 = ctypes.windll.user32
        self._user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self._user32.GetCursorPos.restype = wintypes.BOOL

    def position(self) -> tuple[int, int]:
        point = self._wintypes.POINT()
        if not self._user32.GetCursorPos(ctypes.byref(point)):
            raise OSError("GetCursorPos failed")
        return point.x, point.y

    def buttons(self) -> tuple[str, ...]:
        held = [
            name
            for name, virtual_key in self._VK_BUTTONS.items()
            if self._user32.GetAsyncKeyState(virtual_key) & 0x8000
        ]
        return tuple(held)

    def close(self) -> None:
        pass


class _PynputBackend:
    """Cross-platform fallback. Tracks buttons with a pynput listener."""

    def __init__(self) -> None:
        from pynput import mouse

        self._mouse = mouse.Controller()
        self._pressed: set[str] = set()
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.start()

    def _on_click(self, _x: int, _y: int, button: object, pressed: bool) -> None:
        name = getattr(button, "name", str(button))
        if pressed:
            self._pressed.add(name)
        else:
            self._pressed.discard(name)

    def position(self) -> tuple[int, int]:
        x, y = self._mouse.position
        return int(x), int(y)

    def buttons(self) -> tuple[str, ...]:
        return tuple(sorted(self._pressed))

    def close(self) -> None:
        self._listener.stop()


class MouseTracker:
    """Sample the mouse cursor on a background thread.

    Args:
        hz: Samples per second.
        history: Number of recent samples kept in memory.
        log_path: Optional JSONL file. One line is appended per change of
            position or button state.
        on_sample: Called for every recorded :class:`MouseSample`.
        on_click: Called with a :class:`ClickEvent` for every press/release.

    Samples are only recorded when the position or the button state changes,
    so a stationary mouse does not fill up the history.
    """

    def __init__(
        self,
        *,
        hz: float = DEFAULT_HZ,
        history: int = DEFAULT_HISTORY,
        log_path: str | Path | None = None,
        on_sample: Callable[[MouseSample], None] | None = None,
        on_click: Callable[[ClickEvent], None] | None = None,
    ) -> None:
        if hz <= 0:
            raise ValueError("hz must be positive")
        if history <= 0:
            raise ValueError("history must be positive")

        self.hz = float(hz)
        self.on_sample = on_sample
        self.on_click = on_click

        self._backend = _WindowsBackend() if IS_WINDOWS else _PynputBackend()
        self._log_file = (
            open(log_path, "a", encoding="utf-8") if log_path is not None else None
        )
        self._history: Deque[MouseSample] = deque(maxlen=history)
        self._clicks: Deque[ClickEvent] = deque(maxlen=history)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> "MouseTracker":
        """Start sampling. Returns ``self`` so it can be used inline."""
        if self._thread is not None:
            raise RuntimeError("tracker is already running")
        self._stop.clear()
        self._started_at = time.perf_counter()
        self.sample()  # seed the history so trail() is never empty
        self._thread = threading.Thread(
            target=self._run, name="mouse-tracker", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop sampling and wait for the background thread to exit."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._log_file is not None:
            self._log_file.flush()

    def close(self) -> None:
        """Stop sampling and release the backend and log file."""
        self.stop()
        self._backend.close()
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

    def __enter__(self) -> "MouseTracker":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- reads -------------------------------------------------------------

    def position(self) -> tuple[int, int]:
        """Read the cursor position immediately."""
        return self._backend.position()

    def buttons(self) -> tuple[str, ...]:
        """Read the buttons that are currently held down."""
        return self._backend.buttons()

    def sample(self) -> MouseSample:
        """Read the cursor once and record the sample."""
        if self._started_at is None:
            self._started_at = time.perf_counter()
        x, y = self._backend.position()
        return self._record(x, y, self._backend.buttons())

    @property
    def history(self) -> tuple[MouseSample, ...]:
        """Recorded samples, oldest first."""
        with self._lock:
            return tuple(self._history)

    @property
    def clicks(self) -> tuple[ClickEvent, ...]:
        """Recorded button events, oldest first."""
        with self._lock:
            return tuple(self._clicks)

    def trail(
        self,
        *,
        seconds: float | None = None,
        points: int | None = None,
    ) -> list[tuple[int, int]]:
        """Return recent cursor positions, oldest first.

        Args:
            seconds: Only include samples from the last N seconds.
            points: Only include the N most recent samples.
        """
        with self._lock:
            samples = list(self._history)

        if seconds is not None and self._started_at is not None:
            cutoff = time.perf_counter() - self._started_at - seconds
            samples = [s for s in samples if s.t >= cutoff]
        if points is not None:
            samples = samples[-points:]
        return [(s.x, s.y) for s in samples]

    # -- internals ---------------------------------------------------------

    def _record(
        self, x: int, y: int, buttons: tuple[str, ...]
    ) -> MouseSample:
        assert self._started_at is not None
        now = time.perf_counter() - self._started_at
        sample = MouseSample(x=x, y=y, t=round(now, 6), buttons=buttons)

        events: list[ClickEvent] = []
        with self._lock:
            previous = self._history[-1].buttons if self._history else ()
            for button in buttons:
                if button not in previous:
                    events.append(ClickEvent(x, y, sample.t, button, True))
            for button in previous:
                if button not in buttons:
                    events.append(ClickEvent(x, y, sample.t, button, False))

            self._history.append(sample)
            self._clicks.extend(events)

            if self._log_file is not None:
                self._log_file.write(json.dumps(asdict(sample)) + "\n")
                self._log_file.flush()

        if self.on_sample is not None:
            try:
                self.on_sample(sample)
            except Exception:  # keep the tracking thread alive
                traceback.print_exc()
        if self.on_click is not None:
            for event in events:
                try:
                    self.on_click(event)
                except Exception:
                    traceback.print_exc()
        return sample

    def _run(self) -> None:
        interval = 1.0 / self.hz
        with self._lock:
            last = self._history[-1] if self._history else None
        last_position = (last.x, last.y) if last else None
        last_buttons = last.buttons if last else ()

        next_at = time.perf_counter()
        while not self._stop.is_set():
            try:
                x, y = self._backend.position()
                buttons = self._backend.buttons()
            except Exception:
                traceback.print_exc()
                self._stop.wait(interval)
                next_at = time.perf_counter()
                continue

            if (x, y) != last_position or buttons != last_buttons:
                self._record(x, y, buttons)
                last_position = (x, y)
                last_buttons = buttons

            next_at += interval
            delay = next_at - time.perf_counter()
            if delay > 0:
                self._stop.wait(delay)
            else:
                next_at = time.perf_counter()


def _format_buttons(buttons: tuple[str, ...]) -> str:
    return "+".join(buttons) if buttons else "-"


def _print_loop(tracker: MouseTracker, duration: float | None) -> None:
    started = time.perf_counter()
    try:
        while duration is None or time.perf_counter() - started < duration:
            x, y = tracker.position()
            print(
                f"\r{x:6d}, {y:6d}  [{_format_buttons(tracker.buttons()):<12}]",
                end="",
                flush=True,
            )
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        pass
    finally:
        print()


def _overlay(tracker: MouseTracker, duration: float | None) -> None:
    """Draw the recent trail plus a crosshair in a transparent overlay."""
    import tkinter as tk

    left, top, width, height = screen_rect()
    root = tk.Tk()
    root.title("Mouse tracker")
    root.overrideredirect(True)
    root.geometry(f"{width}x{height}+{left}+{top}")
    root.attributes("-topmost", True)
    root.configure(bg="black")
    if IS_WINDOWS:
        root.attributes("-transparentcolor", "black")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    def redraw() -> None:
        canvas.delete("trail")
        points = tracker.trail(points=180)
        if len(points) >= 2:
            coordinates = [
                value
                for x, y in points
                for value in (x - left, y - top)
            ]
            canvas.create_line(
                *coordinates,
                fill="#ff3366",
                width=3,
                smooth=True,
                capstyle=tk.ROUND,
                tags="trail",
            )

        x, y = tracker.position()
        radius = 12
        canvas.create_oval(
            x - left - radius,
            y - top - radius,
            x - left + radius,
            y - top + radius,
            outline="#00e5ff",
            width=3,
            tags="trail",
        )
        canvas.create_line(
            x - left - radius * 2,
            y - top,
            x - left + radius * 2,
            y - top,
            fill="#00e5ff",
            width=1,
            tags="trail",
        )
        canvas.create_line(
            x - left,
            y - top - radius * 2,
            x - left,
            y - top + radius * 2,
            fill="#00e5ff",
            width=1,
            tags="trail",
        )
        root.after(33, redraw)

    root.bind("<Escape>", lambda _event: root.destroy())
    root.bind("<Button-1>", lambda _event: root.destroy())
    if duration is not None:
        root.after(max(1, int(duration * 1000)), root.destroy)

    root.focus_force()
    redraw()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Track the mouse cursor position and buttons."
    )
    parser.add_argument(
        "--hz",
        type=float,
        default=DEFAULT_HZ,
        help=f"samples per second (default: {DEFAULT_HZ:g})",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="stop after N seconds (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="append JSONL samples to this file",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="draw the cursor trail in a transparent full-screen overlay",
    )
    args = parser.parse_args(argv)

    if not IS_WINDOWS:
        try:
            import pynput  # noqa: F401
        except ImportError:
            parser.error(
                "tracking outside Windows requires pynput: "
                "python -m pip install pynput"
            )

    tracker = MouseTracker(hz=args.hz, log_path=args.log)
    with tracker:
        if args.overlay:
            _overlay(tracker, args.duration)
        else:
            _print_loop(tracker, args.duration)

    if args.log is not None:
        print(f"logged {len(tracker.history)} samples to {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

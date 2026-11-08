import argparse
import math
import sys

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QApplication, QWidget

INK = QColor("#111111")          # crack colour
SHINE = QColor("#e6f3ff")        # thin glass highlight next to each crack
BURST_FILL = QColor("#efe8a0")   # starburst fill
FOOT_FILL = QColor("#fcfcf4")    # foot fill

# Crack pattern settings (everything is fixed: the same kick looks identical every time)
N_MAIN = 13              # number of main cracks radiating from the impact
ROTATION = 0.35          # rotation of the whole pattern, in radians


# --------------------------------------------------------------------------- #
# Fixed "jitter": a formula, not random. Same inputs -> same output, every run.
# --------------------------------------------------------------------------- #
def _u(*keys):
    """Deterministic value in [0, 1) from a few numbers."""
    t = 0.0
    for i, k in enumerate(keys):
        t += (k + 1) * (12.9898 + 7.233 * i)
    v = math.sin(t) * 43758.5453
    return v - math.floor(v)


def _j(*keys):
    """Deterministic value in [-1, 1)."""
    return _u(*keys) * 2 - 1


# --------------------------------------------------------------------------- #
# Crack geometry (pure Python, no GUI -> easy to test)
# --------------------------------------------------------------------------- #
def generate_cracks(w, h, impact):
    """Return a list of segments (x1, y1, x2, y2, dist_from_impact, width),
    sorted by dist so they can be revealed outward from the impact point."""
    cx, cy = impact
    far = max(math.hypot(cx - x, cy - y) for x in (0, w) for y in (0, h))
    segs = []
    spokes = []  # polyline of each main crack, for the web rings

    def walk(x, y, ang, length, width, depth, tag, record=None):
        travelled = 0.0
        pts = [(x, y)]
        k = 0
        while travelled < length:
            step = 22 + 33 * _u(tag, k, 1)
            ang += 0.2 * _j(tag, k, 2)
            nx, ny = x + math.cos(ang) * step, y + math.sin(ang) * step
            wd = max(1.2, width * (1 - 0.55 * travelled / length))
            segs.append((x, y, nx, ny, math.hypot(x - cx, y - cy), wd))
            x, y, travelled = nx, ny, travelled + step
            pts.append((x, y))
            if depth < 2 and k % 7 == 3:                       # a side crack every 7th step
                side = 1 if (k // 7 + tag) % 2 == 0 else -1
                walk(x, y, ang + side * (0.4 + 0.55 * _u(tag, k, 3)),
                     (0.08 + 0.22 * _u(tag, k, 4)) * (length - travelled + 80),
                     wd * 0.65, depth + 1, tag * 37 + k + 1)
            if not (-80 < x < w + 80 and -80 < y < h + 80):
                break
            k += 1
        if record is not None:
            record.extend(pts)

    for i in range(N_MAIN):
        ang = ROTATION + i * math.tau / N_MAIN + 0.18 * _j(i, 0, 5)
        pts = []
        walk(cx, cy, ang, far * (1.0 + 0.2 * _j(i, 0, 6)), 5.0, 0, i + 1, pts)
        spokes.append(pts)

    # concentric web: join neighbouring spokes at a few radii with jagged lines
    for ri, r in enumerate((95, 175, 290, 440, 640, 880)):
        ring = []
        for pts in spokes:
            best = min(pts, key=lambda p: abs(math.hypot(p[0] - cx, p[1] - cy) - r))
            ring.append(best if abs(math.hypot(best[0] - cx, best[1] - cy) - r) < 70 else None)
        for i, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1])):
            if a is None or b is None or _u(ri, i, 7) < 0.3:    # ~30% of links left out
                continue
            x, y = a
            for k in range(1, 4):
                t = k / 3
                nx = a[0] + (b[0] - a[0]) * t + (9 * _j(ri, i, k, 8) if k < 3 else 0)
                ny = a[1] + (b[1] - a[1]) * t + (9 * _j(ri, i, k, 9) if k < 3 else 0)
                segs.append((x, y, nx, ny, float(r), 1.4))
                x, y = nx, ny

    segs.sort(key=lambda s: s[4])
    return segs


# --------------------------------------------------------------------------- #
# Choosing where the crack starts
# --------------------------------------------------------------------------- #
ANCHORS = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.12), "bottom": (0.5, 0.88),
    "left": (0.12, 0.5), "right": (0.88, 0.5),
    "top-left": (0.12, 0.12), "top-right": (0.88, 0.12),
    "bottom-left": (0.12, 0.88), "bottom-right": (0.88, 0.88),
}


def resolve_impact(spec, w, h, pointer=None):
    """Turn an impact spec into pixel coordinates (x, y).

    spec can be: (960, 540) pixels | (0.25, 0.7) fractions of the window |
    "center" / "top-left" / ... | "cursor" | a function returning one of those |
    None (= centre of the window)."""
    if callable(spec):
        spec = spec()
    if spec is None:
        x, y = 0.5 * w, 0.5 * h          # default: centre of the window
    elif isinstance(spec, str):
        key = spec.strip().lower().replace("_", "-").replace(" ", "-")
        if key == "cursor":
            if pointer is None:
                raise ValueError("'cursor' needs a pointer position")
            x, y = pointer
        elif key in ANCHORS:
            fx, fy = ANCHORS[key]
            x, y = fx * w, fy * h
        else:
            raise ValueError(f"unknown impact {spec!r}; try one of "
                             f"{sorted(ANCHORS) + ['cursor']}")
    else:
        a, b = spec
        if isinstance(a, float) and isinstance(b, float) and 0 <= a <= 1 and 0 <= b <= 1:
            x, y = a * w, b * h          # fractions of the window
        else:
            x, y = a, b                  # pixels
    return (min(max(float(x), 0.0), w), min(max(float(y), 0.0), h))


def parse_impact_arg(text):
    """Command-line form: 'center', 'cursor', '500,300' (pixels) or '0.8,0.2' (fractions)."""
    text = text.strip()
    if "," not in text:
        return text
    a, b = (p.strip() for p in text.split(",", 1))
    if "." in a or "." in b:
        return (float(a), float(b))
    return (int(a), int(b))


def _ease_out(t):
    return 1 - (1 - t) ** 2


# --------------------------------------------------------------------------- #
# The effect
# --------------------------------------------------------------------------- #
class CrackedGlass(QWidget):
    """A kick-and-crack effect that plays inside the window you give it.

        glass = CrackedGlass(window)
        glass.play(impact="center")          # returns immediately

    It is a transparent child of `window`, sits on top of its other widgets,
    ignores the mouse, and hides itself again when the animation finishes.
    `impact` / `foot_start` accept pixels, fractions, names like "center" or
    "cursor" (see resolve_impact). Connect to `finished` or pass `on_done`.
    """

    finished = pyqtSignal()

    TICK_MS = 16
    T_REVEAL = 1.0
    T_FADE = 0.8

    def __init__(self, window):
        if not isinstance(window, QWidget):
            raise TypeError("CrackedGlass needs a PyQt6 QWidget window")
        super().__init__(window)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(window.rect())
        self.hide()

        self.playing = False
        self._hold = 2.5
        self._on_done = None
        self._lines = []
        self._burst = QPolygonF()
        self._t = 0.0
        self._kick_secs = 0.0
        self._shown = 0
        self._fx = self._fy = 0.0
        self._start = self._impact = (0.0, 0.0)
        self._landed = True
        self._burst_on = False
        self._foot_on = False

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)

    # -- public --------------------------------------------------------------- #
    def play(self, impact="center", hold=2.5, foot_start=None, kick_secs=0.18,
             on_done=None):
        """Play the kick + crack once. `foot_start` is where the foot lunges from
        (it lands on `impact` after `kick_secs`); `hold` is how long the cracks stay."""
        if self.playing:
            return

        parent = self.parentWidget()
        if parent is None:
            raise RuntimeError("CrackedGlass has no window to play in")

        self.setGeometry(parent.rect())
        self.raise_()
        self.show()

        w, h = self.width(), self.height()
        cursor = self.mapFromGlobal(QCursor.pos())
        pointer = (cursor.x(), cursor.y())

        self._impact = resolve_impact(impact, w, h, pointer=pointer)
        self._start = (self._impact if foot_start is None
                       else resolve_impact(foot_start, w, h, pointer=pointer))
        self._hold = hold
        self._on_done = on_done

        cx, cy = self._impact
        sx, sy = self._start
        self._kick_secs = kick_secs if math.hypot(sx - cx, sy - cy) > 1 else 0.0

        segs = generate_cracks(w, h, self._impact)
        self._far = max(s[4] for s in segs) + 120

        # Pre-build pens/points so paintEvent() only has to draw.
        self._lines = []
        for x1, y1, x2, y2, dist, wd in segs:
            shine_pen = QPen(SHINE, max(1.0, wd * 0.6))
            ink_pen = QPen(INK, wd)
            ink_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            self._lines.append((
                dist,
                QPointF(x1, y1), QPointF(x2, y2),
                QPointF(x1 + 1.5, y1 + 1.5), QPointF(x2 + 1.5, y2 + 1.5),
                shine_pen, ink_pen,
            ))

        self._burst = self._starburst(self._impact)
        self._t = -self._kick_secs
        self._shown = 0
        self._fx, self._fy = sx, sy
        self._landed = self._kick_secs == 0.0
        self._burst_on = False
        self._foot_on = True

        self.playing = True
        self.update()
        self._timer.start()

    # -- animation ------------------------------------------------------------ #
    def _tick(self):
        t = self._t
        changed = False

        if t < 0:                                              # foot lunges to the impact
            p = ((t + self._kick_secs) / self._kick_secs) ** 2  # accelerate into the hit
            sx, sy = self._start
            cx, cy = self._impact
            self._fx, self._fy = sx + (cx - sx) * p, sy + (cy - sy) * p
            changed = True
        else:
            if not self._landed:                                # landed: snap onto the impact
                self._fx, self._fy = self._impact
                self._landed = True
                changed = True
            if not self._burst_on:                              # show the starburst on contact
                self._burst_on = True
                changed = True

            if t < self.T_REVEAL:                               # cracks spread outward
                front = _ease_out(t / self.T_REVEAL) * self._far
                n = self._shown
                while n < len(self._lines) and self._lines[n][0] <= front:
                    n += 1
                if n != self._shown:
                    self._shown = n
                    changed = True
            elif t < self.T_REVEAL + self._hold:                # hold the cracked look
                if self._shown != len(self._lines):
                    self._shown = len(self._lines)
                    changed = True
            elif t < self.T_REVEAL + self._hold + self.T_FADE:  # cracks retract
                if self._shown == len(self._lines) and (self._burst_on or self._foot_on):
                    self._burst_on = False
                    self._foot_on = False
                    changed = True
                k = (t - self.T_REVEAL - self._hold) / self.T_FADE
                n = int(len(self._lines) * (1 - k))
                if n != self._shown:
                    self._shown = n
                    changed = True
            else:
                self._finish()
                return

        self._t += self.TICK_MS / 1000.0
        if changed:
            self.update()

    def _finish(self):
        self._timer.stop()
        self.playing = False
        self.hide()
        callback, self._on_done = self._on_done, None
        self.finished.emit()
        if callback:
            callback()

    # -- drawing helpers ------------------------------------------------------ #
    @staticmethod
    def _starburst(impact):
        cx, cy = impact
        pts = []
        n = 16
        for i in range(n * 2):
            # fixed slight variation in spike length (0.85 - 1.1), same every time
            r = (95 if i % 2 == 0 else 48) * (0.975 + 0.125 * _j(i, 10))
            a = i * math.pi / n
            pts.append(QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r))
        return QPolygonF(pts)

    @staticmethod
    def _foot_shape(cx, cy):
        ang = math.radians(10)
        ca, sa = math.cos(ang), math.sin(ang)

        def rot(x, y):
            return QPointF(cx + x * ca - y * sa, cy + x * sa + y * ca)

        body = QPolygonF([rot(-34, -44), rot(34, -44), rot(34, 44), rot(-34, 44)])
        band = (rot(-34, 26), rot(34, 26))
        return body, band

    # -- painting ------------------------------------------------------------- #
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Crack lines: a pale highlight under a dark line.
        for _dist, p1, p2, sp1, sp2, shine_pen, ink_pen in self._lines[:self._shown]:
            painter.setPen(shine_pen)
            painter.drawLine(sp1, sp2)
            painter.setPen(ink_pen)
            painter.drawLine(p1, p2)

        if self._burst_on:
            pen = QPen(INK, 3)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(BURST_FILL)
            painter.drawPolygon(self._burst)

        if self._foot_on:
            body, band = self._foot_shape(self._fx, self._fy)
            pen = QPen(INK, 5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(FOOT_FILL)
            painter.drawPolygon(body)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(INK, 4))
            painter.drawLine(band[0], band[1])


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Demo: play the cracked-glass kick in a window.")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds before it triggers")
    ap.add_argument("--hold", type=float, default=2.5, help="seconds the cracks stay")
    ap.add_argument("--impact", default="center",
                    help="where the crack starts: center, top-left, cursor, "
                         "500,300 (pixels) or 0.8,0.2 (fractions of the window)")
    ap.add_argument("--x", type=float, default=None,
                    help="crack start X in pixels (use together with --y; overrides --impact)")
    ap.add_argument("--y", type=float, default=None,
                    help="crack start Y in pixels (use together with --x; overrides --impact)")
    ap.add_argument("--foot", default=None,
                    help="where the foot starts (same formats as --impact); default: at the impact")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the resolved crack start and exit without playing")
    a = ap.parse_args()

    if (a.x is None) != (a.y is None):
        ap.error("--x and --y must be given together")

    impact_spec = (a.x, a.y) if a.x is not None else parse_impact_arg(a.impact)
    foot_spec = parse_impact_arg(a.foot) if a.foot else None

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Cracked Glass")
    window.resize(960, 600)
    window.setStyleSheet("background-color: #b9c8d4;")

    glass = CrackedGlass(window)

    if a.dry_run:
        try:
            x, y = resolve_impact(impact_spec, window.width(), window.height())
        except ValueError as exc:
            sys.exit(f"error: {exc}")
        print(f"window {window.width()}x{window.height()}; "
              f"crack would start at ({x:.0f}, {y:.0f})")
        sys.exit(0)

    window.show()
    print(f"Kicking the window in {a.delay:g}s...")
    QTimer.singleShot(
        int(a.delay * 1000),
        lambda: glass.play(impact=impact_spec, hold=a.hold,
                           foot_start=foot_spec, on_done=app.quit),
    )
    sys.exit(app.exec())

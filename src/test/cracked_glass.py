import math
import sys

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
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
def _generate_cracks(w, h, impact):
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


def _ease_out(t):
    return 1 - (1 - t) ** 2


# --------------------------------------------------------------------------- #
# The effect (one hidden overlay per window, managed by the function below)
# --------------------------------------------------------------------------- #
class _CrackedGlass(QWidget):
    TICK_MS = 16
    T_REVEAL = 1.0
    T_FADE = 0.8

    def __init__(self, window):
        super().__init__(window)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(window.rect())
        self.hide()

        self.playing = False
        self._hold = 2.5
        self._on_done = None
        self._lines = []
        self._burst = QPolygonF()
        self._impact = (0.0, 0.0)
        self._far = 0.0
        self._t = 0.0
        self._shown = 0
        self._marks_on = False

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)

    def play(self, x, y, hold=2.5, on_done=None):
        if self.playing:
            return

        parent = self.parentWidget()
        if parent is None:
            raise RuntimeError("the effect has no window to play in")

        self.setGeometry(parent.rect())
        self.raise_()
        self.show()

        w, h = self.width(), self.height()
        self._impact = (min(max(float(x), 0.0), float(w)),
                        min(max(float(y), 0.0), float(h)))
        self._hold = hold
        self._on_done = on_done

        segs = _generate_cracks(w, h, self._impact)
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
        self._t = 0.0
        self._shown = 0
        self._marks_on = True

        self.playing = True
        self.update()
        self._timer.start()

    def _tick(self):
        t = self._t
        changed = False

        if t < self.T_REVEAL:                                   # cracks spread outward
            front = _ease_out(t / self.T_REVEAL) * self._far
            n = self._shown
            while n < len(self._lines) and self._lines[n][0] <= front:
                n += 1
            if n != self._shown:
                self._shown = n
                changed = True
        elif t < self.T_REVEAL + self._hold:                    # hold the cracked look
            if self._shown != len(self._lines):
                self._shown = len(self._lines)
                changed = True
        elif t < self.T_REVEAL + self._hold + self.T_FADE:      # cracks retract
            if self._marks_on:
                self._marks_on = False
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
        if callback:
            callback()

    # -- drawing -------------------------------------------------------------- #
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Crack lines: a pale highlight under a dark line.
        for _dist, p1, p2, sp1, sp2, shine_pen, ink_pen in self._lines[:self._shown]:
            painter.setPen(shine_pen)
            painter.drawLine(sp1, sp2)
            painter.setPen(ink_pen)
            painter.drawLine(p1, p2)

        if self._marks_on:
            pen = QPen(INK, 3)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(BURST_FILL)
            painter.drawPolygon(self._burst)

            body, band = self._foot_shape(*self._impact)
            pen = QPen(INK, 5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(FOOT_FILL)
            painter.drawPolygon(body)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(INK, 4))
            painter.drawLine(band[0], band[1])


# --------------------------------------------------------------------------- #
# Public API: one function
# --------------------------------------------------------------------------- #
def play_cracked_glass(window, x, y, hold=2.5, on_done=None):
    """Kick the glass in `window` at window-relative pixel (x, y).

    Call it from the GUI thread; it returns immediately and animates via a
    QTimer. The effect is drawn inside the window on top of its other widgets
    and ignores the mouse. If the effect is already playing in that window the
    call is ignored. `hold` is how long the cracks stay visible; `on_done` is
    called when the animation is over.
    """
    if not isinstance(window, QWidget):
        raise TypeError("play_cracked_glass needs a PyQt6 QWidget window")

    effect = getattr(window, "_cracked_glass_effect", None)
    if effect is None:
        effect = _CrackedGlass(window)
        window._cracked_glass_effect = effect

    effect.play(x, y, hold=hold, on_done=on_done)
    return effect


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Cracked Glass")
    window.resize(960, 600)
    window.setStyleSheet("background-color: #b9c8d4;")
    window.show()

    QTimer.singleShot(
        800,
        lambda: play_cracked_glass(window, 480, 300, on_done=app.quit),
    )
    sys.exit(app.exec())

"""
timer_widget.py - Draggable floating countdown HUD.
"""

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QMouseEvent


class DraggableCountdownWidget(QWidget):
    """
    Floating, translucent countdown widget positioned at the top-right.
    Draggable by the user anywhere on screen. Emits `timeout` when hitting 0.
    """
    timeout = pyqtSignal()

    def __init__(self, duration_seconds: int, parent=None):
        super().__init__(parent)
        self.remaining_seconds = max(0, duration_seconds)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(140, 40)

        # Layout & Label
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel(self._format_time(self.remaining_seconds), self)
        self.label.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.label.setStyleSheet("color: #F8FAFC; background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        # Dragging variables
        self._dragging = False
        self._drag_start_pos = QPoint()

        # 1-second interval timer
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        if self.remaining_seconds > 0:
            self._timer.start()

    def _format_time(self, seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.label.setText(self._format_time(self.remaining_seconds))
            if self.remaining_seconds <= 10:
                # Warning flash style in the final 10 seconds
                self.label.setStyleSheet("color: #EF4444; background: transparent;")
            self.update()

        if self.remaining_seconds <= 0:
            self._timer.stop()
            self.timeout.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Rounded dark capsule background
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 20, 20)
        painter.fillPath(path, QColor(24, 24, 27, 230))
        painter.setPen(QPen(QColor(99, 102, 241, 200), 1.5))
        painter.drawPath(path)

    # ---------------- Drag-and-Drop Handlers ----------------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.unsetCursor()
            event.accept()
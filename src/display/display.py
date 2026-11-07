import os
import re
import sys
from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget
from mascot import Mascot

DEBUG = True


def log(*args):
  if DEBUG:
    print("[mascot]", *args)
    sys.stdout.flush()


# ------------------------------- Tweaks ----------------------------------
MASCOT_SCALE = 0.35
INPUT_BOX = (0.272, 0.020, 0.776, 0.800)  # (left, top, right, bottom) fractions
INPUT_PADDING = 14  # screen px padding inside input area
INPUT_FONT_PX = 70  # natural px, scaled by MASCOT_SCALE
INPUT_TEXT_COLOR = QColor(0x13, 0x13, 0x13)
CARET_BLINK_MS = 530


class MascotDisplay(QWidget):
  """Fullscreen transparent, stay-on-top window displaying an interactive mascot.

  Preserves the exact API:
      MascotDisplay(scale=..., title=..., onSubmit=...).run()
  """

  # Signal allowing background worker threads (like pipeline.py) to push speech and mood
  ai_response_signal = pyqtSignal(str, str)

  def __init__(
      self,
      scale: float = MASCOT_SCALE,
      title: str = "Python Window",
      className: str = "MainWin",
      onSubmit=None,
      sprite_folder: str = None,
  ):
    # Ensure a QApplication instance exists before widget creation
    self._app = QApplication.instance()
    self._owns_app = False
    if self._app is None:
      self._app = QApplication(sys.argv)
      self._owns_app = True

    super().__init__()
    self.setWindowTitle(title)
    self.scale = scale
    self.onSubmit = onSubmit

    # 1. Native Window Configuration
    self.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # 2. State & Mascot setup
    self.mascot = (
        Mascot(base_sprite_dir=sprite_folder)
        if sprite_folder
        else Mascot()
    )
    self.currentSprite = None
    self.spriteCache = {}  # path -> QPixmap

    self.previousState = self.mascot.getState()
    self.isScrolling = False

    # Mascot coordinates inside window
    self.mascotX = 0
    self.mascotY = 0

    # Dragging mechanics
    self.dragging = False
    self.dragMoved = False
    self.dragStartX = 0
    self.dragStartY = 0
    self.dragMascotX = 0
    self.dragMascotY = 0
    self.dragThreshold = QApplication.startDragDistance()

    # Text Input & Caret
    self.inputText = ""
    self.caretOn = True
    self.fontPx = max(10, int(INPUT_FONT_PX * self.scale))
    self.font = QFont("Segoe UI", pointSize=-1)
    self.font.setPixelSize(self.fontPx)

    # Bubble text buffer (for incoming AI dialogue)
    self.bubbleText = ""

    # Connect background thread signal
    self.ai_response_signal.connect(self.setSpeech)

    # Caret Blink Timer
    self.caretTimer = QTimer(self)
    self.caretTimer.setInterval(CARET_BLINK_MS)
    self.caretTimer.timeout.connect(self._onCaretTick)
    self.caretTimer.start()

  # ------------------------------------------------------------- Lifecycle
  def run(self) -> int:
    """Sizes window to primary screen, initializes sprite, shows window, and runs loop."""
    screen_geo = QApplication.primaryScreen().geometry()
    self.setGeometry(screen_geo)

    first = self.mascot.getNextImage()
    if not first:
      raise RuntimeError(f"Mascot.getNextImage() returned {first!r}")

    self.currentSprite = str(first)
    log("first sprite:", self.currentSprite)

    drawW, drawH = self._spriteSize(self.currentSprite)
    self.mascotX = (self.width() - drawW) // 2
    self.mascotY = (self.height() - drawH) // 2

    self.show()
    self.raise_()
    self.activateWindow()

    if self._owns_app:
      return self._app.exec()
    return 0

  # ---------------------------------------------------------- AI Integration
  def setSpeech(self, text: str, reaction: str = ""):
    """Thread-safe handler to set mood and display AI speech text."""
    self.bubbleText = text
    if reaction and hasattr(self.mascot, "setReaction"):
      self.mascot.setReaction(reaction)
    self._setSprite(self.mascot.getNextImage())
    self.update()

  # ------------------------------------------------------------- Sprites
  def _loadSprite(self, path: str) -> QPixmap:
    pix = self.spriteCache.get(path)
    if pix is None:
      if not os.path.exists(path):
        raise FileNotFoundError(f"Sprite not found: '{path}'")
      raw_pix = QPixmap(path)
      # Pre-scale pixmap with smooth bicubic bilinear filter for efficiency
      target_w = max(1, int(raw_pix.width() * self.scale))
      target_h = max(1, int(raw_pix.height() * self.scale))
      pix = raw_pix.scaled(
          target_w,
          target_h,
          Qt.AspectRatioMode.IgnoreAspectRatio,
          Qt.TransformationMode.SmoothTransformation,
      )
      self.spriteCache[path] = pix
    return pix

  def _spriteSize(self, path: str) -> tuple[int, int]:
    pix = self._loadSprite(path)
    return pix.width(), pix.height()

  def _setSprite(self, path: str):
    """Swap current sprite, anchoring the center coordinate on screen."""
    if not path:
      log(f"getNextImage() returned {path!r}; keeping current sprite")
      return
    path = str(path)
    if path == self.currentSprite:
      return
    log("sprite ->", path)

    if self.currentSprite is None:
      self.currentSprite = path
      return

    oldW, oldH = self._spriteSize(self.currentSprite)
    cx = self.mascotX + oldW // 2
    cy = self.mascotY + oldH // 2

    self.currentSprite = path
    newW, newH = self._spriteSize(path)
    self._moveMascot(cx - newW // 2, cy - newH // 2)

  def _moveMascot(self, x: int, y: int) -> bool:
    """Clamp mascot sprite within screen bounds."""
    drawW, drawH = self._spriteSize(self.currentSprite)
    clamped_x = min(max(x, 0), max(0, self.width() - drawW))
    clamped_y = min(max(y, 0), max(0, self.height() - drawH))

    if (clamped_x, clamped_y) == (self.mascotX, self.mascotY):
      return False

    self.mascotX, self.mascotY = clamped_x, clamped_y
    return True

  # ------------------------------------------------------------ Text Input
  def _inputRect(self) -> QRect | None:
    if not self.isScrolling or self.currentSprite is None:
      return None
    w, h = self._spriteSize(self.currentSprite)
    l, t, r, b = INPUT_BOX
    return QRect(
        self.mascotX + int(l * w),
        self.mascotY + int(t * h),
        int((r - l) * w),
        int((b - t) * h),
    )

  def _inInput(self, x: int, y: int) -> bool:
    rect = self._inputRect()
    return rect is not None and rect.contains(x, y)

  def _wrapLines(self, text: str, maxWidth: int) -> list[str]:
    """Word-wraps input text and splits oversized continuous tokens."""
    metrics = QFontMetrics(self.font)
    lines = []
    current = ""

    for token in re.findall(r"\s+|\S+", text):
      if token.isspace():
        current += token
        continue
      if current.strip() and metrics.horizontalAdvance(current + token) > maxWidth:
        lines.append(current)
        current = ""
      if metrics.horizontalAdvance(current + token) <= maxWidth:
        current += token
        continue
      # Break individual long token by character
      for ch in token:
        if current and metrics.horizontalAdvance(current + ch) > maxWidth:
          lines.append(current)
          current = ""
        current += ch
    lines.append(current)
    return lines

  def _submit(self):
    text = self.inputText
    self.inputText = ""
    self.caretOn = True

    if text.strip() and self.onSubmit is not None:
      self.onSubmit(text)

    self.isScrolling = False
    self.mascot.setState(self.previousState)
    self._setSprite(self.mascot.getNextImage())
    self.update()

  def _onCaretTick(self):
    if self.isScrolling:
      self.caretOn = not self.caretOn
      self.update()

  def _onClick(self):
    """Toggles scroll mode on simple mouse clicks."""
    self.isScrolling = not self.isScrolling
    log("scrolling =", self.isScrolling)

    if self.isScrolling:
      self.previousState = self.mascot.getState()
      self.mascot.setState(Mascot.SCROLL)
    else:
      self.mascot.setState(self.previousState)
      self.inputText = ""

    self._setSprite(self.mascot.getNextImage())
    self.update()

  # ------------------------------------------------------------- Painting
  def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # 1. Draw Sprite
    if self.currentSprite:
      pix = self._loadSprite(self.currentSprite)
      painter.drawPixmap(self.mascotX, self.mascotY, pix)

    # 2. Draw Typed Text & Caret (when SCROLL mode is active)
    rect = self._inputRect()
    if rect is not None:
      box = rect.adjusted(
          INPUT_PADDING, INPUT_PADDING, -INPUT_PADDING, -INPUT_PADDING
      )
      if box.width() > 0 and box.height() > 0:
        painter.save()
        painter.setClipRect(box)
        painter.setFont(self.font)

        metrics = QFontMetrics(self.font)
        lineH = metrics.height()
        caretW = max(2, int(self.fontPx * 0.07))

        lines = self._wrapLines(self.inputText, box.width() - caretW)
        y0 = box.top() + min(0, box.height() - len(lines) * lineH)

        painter.setPen(INPUT_TEXT_COLOR)
        for i, line in enumerate(lines):
          y = y0 + i * lineH
          baseline = y + metrics.ascent()
          if line and y + lineH >= box.top() and y <= box.bottom():
            painter.drawText(box.left(), baseline, line)

        # Draw Caret
        if self.caretOn:
          lastW = metrics.horizontalAdvance(lines[-1]) if lines[-1] else 0
          caretH = int(lineH * 0.85)
          caretY = y0 + (len(lines) - 1) * lineH + (lineH - caretH) // 2
          caretX = box.left() + lastW

          painter.fillRect(
              caretX, caretY, caretW, caretH, INPUT_TEXT_COLOR
          )

        painter.restore()

  # ------------------------------------------------------- Event Handlers
  def mousePressEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton:
      pos = event.position().toPoint()
      w, h = self._spriteSize(self.currentSprite)
      sprite_rect = QRect(self.mascotX, self.mascotY, w, h)

      # Only capture mouse presses on the mascot itself
      if sprite_rect.contains(pos):
        self.dragging = True
        self.dragMoved = False
        self.dragStartX = pos.x()
        self.dragStartY = pos.y()
        self.dragMascotX = self.mascotX
        self.dragMascotY = self.mascotY
        event.accept()
        return

    super().mousePressEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent):
    if self.dragging:
      pos = event.position().toPoint()
      dx = pos.x() - self.dragStartX
      dy = pos.y() - self.dragStartY

      if not self.dragMoved:
        if abs(dx) > self.dragThreshold or abs(dy) > self.dragThreshold:
          self.dragMoved = True
          self.setCursor(Qt.CursorShape.SizeAllCursor)

      if self.dragMoved:
        if self._moveMascot(self.dragMascotX + dx, self.dragMascotY + dy):
          self.update()
      event.accept()
      return

    super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton and self.dragging:
      wasClick = not self.dragMoved
      self.dragging = False
      self.unsetCursor()

      pos = event.position().toPoint()
      # Clicks outside the scroll box toggle scroll mode
      if wasClick and not self._inInput(pos.x(), pos.y()):
        self._onClick()

      event.accept()
      return

    super().mouseReleaseEvent(event)

  def keyPressEvent(self, event):
    key = event.key()

    if key == Qt.Key.Key_Escape:
      self.close()
      event.accept()
      return

    if self.isScrolling:
      if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        self._submit()
        event.accept()
        return
      elif key == Qt.Key.Key_Backspace:
        self.inputText = self.inputText[:-1]
        self.caretOn = True
        self.update()
        event.accept()
        return

      text = event.text()
      if text and text.isprintable():
        self.inputText += text
        self.caretOn = True
        self.update()
        event.accept()
        return

    super().keyPressEvent(event)


def handleSubmit(text):
  print("submitted:", text)


def main():
  return MascotDisplay(onSubmit=handleSubmit).run()


if __name__ == "__main__":
  print("display.py loaded from", os.path.abspath(__file__))
  sys.exit(main())
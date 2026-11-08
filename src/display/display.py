import ctypes
import os
import random
import re
import sys
from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
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
user32 = ctypes.windll.user32
SCREEN_WIDTH = user32.GetSystemMetrics(0)
SCREEN_HEIGHT = user32.GetSystemMetrics(1)

MASCOT_SCALE = (SCREEN_WIDTH / 1067) * 0.15
INPUT_BOX = (0.272, 0.020, 0.776, 0.800)  # (left, top, right, bottom) fractions
INPUT_PADDING = 14  # screen px padding inside input area
INPUT_FONT_PX = 70  # natural px, scaled by MASCOT_SCALE
INPUT_TEXT_COLOR = QColor(0x13, 0x13, 0x13)
CARET_BLINK_MS = 530

# Wandering
WANDER_INTERVAL_MS = 33  # ~30 ticks/sec
WANDER_TURN_TICKS = (60, 90)  # re-pick direction every 2-3 seconds
WANDER_VX_CHOICES = (-2, -1, 0, 1, 2)  # px per tick
WANDER_VY_CHOICES = (0,)  # horizontal roaming line
DRAG_COOLDOWN_TICKS = 90  # pause wandering ~3s after drop

# UI Dimensions
POKE_BTN_W = 115
POKE_BTN_H = 30
SPEECH_DISMISS_MS = 8000  # Hide bubble after 8 seconds


class MascotDisplay(QWidget):
  """Fullscreen transparent, stay-on-top window displaying an interactive mascot."""

  ai_response_signal = pyqtSignal(str, str)

  def isInputActive(self) -> bool:
    """Returns True if the mascot is currently in SCROLL mode (typing input open)."""
    return bool(self.isScrolling)

  def __init__(
      self,
      scale: float = MASCOT_SCALE,
      title: str = "Python Window",
      className: str = "MainWin",
      onSubmit=None,
      onPoke=None,
      sprite_folder: str = None,
  ):
    self._app = QApplication.instance()
    self._owns_app = False
    if self._app is None:
      self._app = QApplication(sys.argv)
      self._owns_app = True

    super().__init__()
    self.setWindowTitle(title)
    self.scale = scale
    self.onSubmit = onSubmit
    self.onPoke = onPoke  # Callback to force Gemini speech

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
        Mascot(base_sprite_dir=sprite_folder) if sprite_folder else Mascot()
    )
    self.currentSprite = None
    self.spriteCache = {}

    self.previousState = self.mascot.getState()
    self.isScrolling = False

    def isInputActive(self) -> bool:
        """Returns True if the mascot is currently in SCROLL mode (typing input open)."""
        return bool(self.isScrolling)

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

    # Autonomous wandering
    self.vx = 0
    self.vy = 0
    self.stepCounter = 0
    self.turnAt = random.randint(*WANDER_TURN_TICKS)
    self.dragCooldown = 0

    # Text Input & Caret
    self.inputText = ""
    self.caretOn = True
    self.fontPx = max(10, int(INPUT_FONT_PX * self.scale))
    self.font = QFont("Segoe UI", pointSize=-1)
    self.font.setPixelSize(self.fontPx)

    # Bubble text buffer & display font
    self.bubbleText = ""
    self.bubbleFont = QFont("Segoe UI", 10, QFont.Weight.Medium)

    # Connect background thread signal
    self.ai_response_signal.connect(self.setSpeech)

    # Caret Blink Timer
    self.caretTimer = QTimer(self)
    self.caretTimer.setInterval(CARET_BLINK_MS)
    self.caretTimer.timeout.connect(self._onCaretTick)
    self.caretTimer.start()

    # Speech Bubble Auto-Dismiss Timer
    self.speechTimer = QTimer(self)
    self.speechTimer.setSingleShot(True)
    self.speechTimer.timeout.connect(self._dismissSpeech)

    # Wander Timer
    self.wanderTimer = QTimer(self)
    self.wanderTimer.setInterval(WANDER_INTERVAL_MS)
    self.wanderTimer.timeout.connect(self._updateWander)
  # ------------------------------------------------------------- Lifecycle
  def run(self) -> int:
    screen_geo = QApplication.primaryScreen().geometry()
    self.setGeometry(screen_geo)

    first = self.mascot.getNextImage()
    if not first:
      raise RuntimeError(f"Mascot.getNextImage() returned {first!r}")

    self.currentSprite = str(first)
    log("first sprite:", self.currentSprite)

    drawW, drawH = self._spriteSize(self.currentSprite)
    bounds = self._wanderBounds()
    self.mascotX = (self.width() - drawW) // 2
    self.mascotY = bounds.y() + bounds.height() - drawH

    self.show()
    self.raise_()
    self.activateWindow()
    self.wanderTimer.start()

    if self._owns_app:
      return self._app.exec()
    return 0

  # ---------------------------------------------------------- AI Integration
  def setSpeech(self, text: str, reaction: str = ""):
    """Thread-safe handler to set mood and display AI speech text."""
    self.bubbleText = text.strip()
    if reaction and hasattr(self.mascot, "setReaction"):
      self.mascot.setReaction(reaction)
    self._setSprite(self.mascot.getNextImage())

    # Stop roaming briefly while speaking
    self.dragCooldown = DRAG_COOLDOWN_TICKS * 2
    self.vx = self.vy = 0

    self.speechTimer.stop()
    if self.bubbleText:
      self.speechTimer.start(SPEECH_DISMISS_MS)

    self.update()

  def _dismissSpeech(self):
    self.bubbleText = ""
    self.update()

  # --------------------------------------------------------------- Wandering
  def _wanderBounds(self) -> QRect:
    screen = self.screen()
    avail = screen.availableGeometry()
    geo = screen.geometry()
    return QRect(
        avail.x() - geo.x(),
        avail.y() - geo.y(),
        avail.width(),
        avail.height(),
    )

  def _updateWander(self):
    if self.dragging or self.isScrolling or self.currentSprite is None:
      return

    if self.dragCooldown > 0:
      self.dragCooldown -= 1
      return

    self.stepCounter += 1
    if self.stepCounter > self.turnAt:
      self.stepCounter = 0
      self.turnAt = random.randint(*WANDER_TURN_TICKS)
      self.vx = random.choice(WANDER_VX_CHOICES)
      self.vy = random.choice(WANDER_VY_CHOICES)

    if self.vx == 0 and self.vy == 0:
      return

    drawW, drawH = self._spriteSize(self.currentSprite)
    bounds = self._wanderBounds()
    minX = bounds.x()
    minY = bounds.y() + 100  # Leave room for floating speech bubble / poke button
    maxX = bounds.x() + bounds.width() - drawW
    maxY = bounds.y() + bounds.height() - drawH

    newX = self.mascotX + self.vx
    newY = self.mascotY + self.vy

    if newX <= minX:
      newX = minX
      self.vx = abs(self.vx)
    elif newX >= maxX:
      newX = maxX
      self.vx = -abs(self.vx)

    if newY <= minY:
      newY = minY
      self.vy = abs(self.vy)
    elif newY >= maxY:
      newY = maxY
      self.vy = -abs(self.vy)

    # Full repaint dirty rect including floating overlays
    old_dirty = self._activeMascotBounds()
    if self._moveMascot(newX, newY):
      new_dirty = self._activeMascotBounds()
      self.update(old_dirty.united(new_dirty))

  # ------------------------------------------------------------- Sprites
  def _loadSprite(self, path: str) -> QPixmap:
    pix = self.spriteCache.get(path)
    if pix is None:
      if not os.path.exists(path):
        raise FileNotFoundError(f"Sprite not found: '{path}'")
      raw_pix = QPixmap(path)
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
    if not path:
      return
    path = str(path)
    if path == self.currentSprite:
      return

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
    drawW, drawH = self._spriteSize(self.currentSprite)
    bounds = self._wanderBounds()

    clamped_x = min(
        max(x, bounds.x()), max(bounds.x(), bounds.x() + bounds.width() - drawW)
    )
    clamped_y = min(
        max(y, bounds.y() + 80),
        max(bounds.y() + 80, bounds.y() + bounds.height() - drawH),
    )

    if (clamped_x, clamped_y) == (self.mascotX, self.mascotY):
      return False

    self.mascotX, self.mascotY = clamped_x, clamped_y
    return True

  # ------------------------------------------------------------ Geometry Helpers
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

  def _pokeButtonRect(self) -> QRect:
    drawW, _ = self._spriteSize(self.currentSprite)
    btn_x = self.mascotX + (drawW - POKE_BTN_W) // 2
    btn_y = self.mascotY - POKE_BTN_H - 10
    return QRect(btn_x, btn_y, POKE_BTN_W, POKE_BTN_H)

  def _inPokeButton(self, x: int, y: int) -> bool:
    return self._pokeButtonRect().contains(x, y)

  def _speechBubbleRect(self) -> QRect:
    if not self.bubbleText:
      return QRect()
    metrics = QFontMetrics(self.bubbleFont)
    max_bubble_w = 300
    wrapped = self._wrapLines(self.bubbleText, max_bubble_w - 20)
    bubble_w = min(
        max_bubble_w, max([metrics.horizontalAdvance(line) for line in wrapped] + [120]) + 24
    )
    bubble_h = len(wrapped) * (metrics.height() + 2) + 40

    drawW, _ = self._spriteSize(self.currentSprite)
    bx = self.mascotX + (drawW - bubble_w) // 2
    by = self.mascotY - POKE_BTN_H - bubble_h - 18
    return QRect(bx, by, bubble_w, bubble_h)

  def _activeMascotBounds(self) -> QRect:
    """Calculates entire bounding box covering sprite + button + speech bubble."""
    w, h = self._spriteSize(self.currentSprite)
    base = QRect(self.mascotX, self.mascotY, w, h)
    base = base.united(self._pokeButtonRect())
    if self.bubbleText:
      base = base.united(self._speechBubbleRect())
    return base.adjusted(-10, -10, 10, 10)

  # ------------------------------------------------------------ Text & Caret
  def _wrapLines(self, text: str, maxWidth: int) -> list[str]:
    metrics = QFontMetrics(self.font)
    lines = []
    current = ""
    for token in re.findall(r"\s+|\S+", text):
      if token.isspace():
        current += token
        continue
      if (
          current.strip()
          and metrics.horizontalAdvance(current + token) > maxWidth
      ):
        lines.append(current)
        current = ""
      if metrics.horizontalAdvance(current + token) <= maxWidth:
        current += token
        continue
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
      self.update(self._inputRect() or self.rect())

  def _onClick(self):
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

    # 1. Draw Mascot Sprite
    if self.currentSprite:
      pix = self._loadSprite(self.currentSprite)
      painter.drawPixmap(self.mascotX, self.mascotY, pix)

    # 2. Draw 'Poke / Speak' Pill Button
    btn_r = self._pokeButtonRect()
    btn_path = QPainterPath()
    btn_path.addRoundedRect(QRectF(btn_r), 15, 15)
    painter.fillPath(btn_path, QColor(30, 33, 40, 230))
    painter.setPen(QPen(QColor(99, 102, 241, 230), 1.5))
    painter.drawPath(btn_path)

    painter.setPen(QColor(245, 245, 245))
    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
    painter.drawText(btn_r, Qt.AlignmentFlag.AlignCenter, "Poke / Speak 💬")

    # 3. Draw AI Speech Bubble (if active)
    if self.bubbleText:
      sb_r = self._speechBubbleRect()
      sb_path = QPainterPath()
      sb_path.addRoundedRect(QRectF(sb_r), 12, 12)
      painter.fillPath(sb_path, QColor(255, 255, 255, 245))
      painter.setPen(QPen(QColor(30, 30, 30, 180), 1.5))
      painter.drawPath(sb_path)

      painter.setFont(self.bubbleFont)
      painter.setPen(QColor(20, 20, 20))
      metrics = QFontMetrics(self.bubbleFont)
      lines = self._wrapLines(self.bubbleText, sb_r.width() - 20)
      line_h = metrics.height() + 2
      y_cur = sb_r.top() + 10 + metrics.ascent()

      for line in lines:
        painter.drawText(sb_r.left() + 12, y_cur, line)
        y_cur += line_h

    # 4. Draw Typed Text & Caret (Scroll Input Mode)
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

        if self.caretOn:
          lastW = metrics.horizontalAdvance(lines[-1]) if lines[-1] else 0
          caretH = int(lineH * 0.85)
          caretY = y0 + (len(lines) - 1) * lineH + (lineH - caretH) // 2
          caretX = box.left() + lastW
          painter.fillRect(caretX, caretY, caretW, caretH, INPUT_TEXT_COLOR)

        painter.restore()

  # ------------------------------------------------------- Event Handlers
  def mousePressEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton:
      pos = event.position().toPoint()

      # 1. Poke Button Click
      if self._inPokeButton(pos.x(), pos.y()):
        if self.onPoke:
          self.onPoke()
        event.accept()
        return

      # 2. Mascot Drag Initiation
      w, h = self._spriteSize(self.currentSprite)
      sprite_rect = QRect(self.mascotX, self.mascotY, w, h)
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
        old_area = self._activeMascotBounds()
        if self._moveMascot(self.dragMascotX + dx, self.dragMascotY + dy):
          new_area = self._activeMascotBounds()
          self.update(old_area.united(new_area))
      event.accept()
      return

    super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent):
    if event.button() == Qt.MouseButton.LeftButton and self.dragging:
      wasClick = not self.dragMoved
      self.dragging = False
      self.unsetCursor()

      if not wasClick:
        self.dragCooldown = DRAG_COOLDOWN_TICKS
        self.vx = self.vy = 0

      pos = event.position().toPoint()
      if (
          wasClick
          and not self._inInput(pos.x(), pos.y())
          and not self._inPokeButton(pos.x(), pos.y())
      ):
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
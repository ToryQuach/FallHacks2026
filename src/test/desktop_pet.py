import os
import random
import sys
from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget


class DesktopPet(QWidget):

  def __init__(self, sprite_path="pet.png"):
    super().__init__()
    self.sprite_path = sprite_path

    # 1. Window Flags: Frameless, stays on top of all windows, excluded from Alt+Tab
    self.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )

    # 2. Transparent background: Transparent pixels let mouse events pass straight through
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # State variables for dragging
    self.is_dragging = False
    self.drag_offset = QPoint()
    self.drag_cooldown = 0  # Pause wandering right after being placed

    # Load or generate sprite
    self.sprite = self.load_or_create_sprite()
    self.resize(self.sprite.size())

    # Start near the bottom-right of the primary screen
    screen = QApplication.primaryScreen().availableGeometry()
    self.move(screen.width() - 250, screen.height() - 250)

    # Wandering physics variables
    self.vx = 2  # Current X speed
    self.vy = 0  # Current Y speed
    self.step_counter = 0

    # 3. Game/Wander Loop (runs at ~30 FPS)
    self.wander_timer = QTimer(self)
    self.wander_timer.timeout.connect(self.update_wander)
    self.wander_timer.start(33)  # ~30 ms

  def load_or_create_sprite(self) -> QPixmap:
    """Loads target PNG, or generates an interactive placeholder if not present."""
    if os.path.exists(self.sprite_path):
      pixmap = QPixmap(self.sprite_path)
      # Optional: scale if the asset is too massive
      if pixmap.width() > 200 or pixmap.height() > 200:
        pixmap = pixmap.scaled(
            140,
            140,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
      return pixmap

    # Fallback: Procedurally draw a circular 120x120 sprite with clear alpha surroundings
    size = 120
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Solid circular body (catches mouse clicks)
    painter.setBrush(QColor(60, 60, 80, 230))
    painter.setPen(QColor(255, 255, 255, 200))
    painter.drawEllipse(10, 10, size - 20, size - 20)

    # Visual icon
    painter.setFont(QFont("Segoe UI Emoji", 40))
    painter.drawText(
        QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "👾"
    )
    painter.end()
    return pixmap

  # --- Paint Event ---
  def paintEvent(self, event):
    painter = QPainter(self)
    painter.drawPixmap(0, 0, self.sprite)

  # --- Mouse Dragging Handlers ---
  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.is_dragging = True
      # Vector distance between cursor and window top-left corner
      self.drag_offset = (
          event.globalPosition().toPoint() - self.frameGeometry().topLeft()
      )
      event.accept()

  def mouseMoveEvent(self, event):
    if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
      # Reposition window along with cursor
      self.move(event.globalPosition().toPoint() - self.drag_offset)
      event.accept()

  def mouseReleaseEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.is_dragging = False
      # Set a 2-second rest cooldown before resuming random movement
      self.drag_cooldown = 60
      event.accept()

  # --- Autonomous Wandering Engine ---
  def update_wander(self):
    # Pause autonomous wander while the user is actively dragging the character
    if self.is_dragging:
      return

    # Decrement drag cooldown
    if self.drag_cooldown > 0:
      self.drag_cooldown -= 1
      return

    # Randomly change direction or pause every ~60-90 ticks (2-3 seconds)
    self.step_counter += 1
    if self.step_counter > random.randint(60, 90):
      self.step_counter = 0
      # Pick new velocity: walk left, walk right, or idle
      self.vx = random.choice([-2, -1, 0, 1, 2])
      self.vy = random.choice([-1, 0, 1])

    # Calculate tentative next position
    new_x = self.x() + self.vx
    new_y = self.y() + self.vy

    # Screen boundary detection: bounce back if hitting monitor edges
    screen = self.screen().availableGeometry()

    if new_x <= screen.left():
      new_x = screen.left()
      self.vx = abs(self.vx)
    elif new_x + self.width() >= screen.right():
      new_x = screen.right() - self.width()
      self.vx = -abs(self.vx)

    if new_y <= screen.top():
      new_y = screen.top()
      self.vy = abs(self.vy)
    elif new_y + self.height() >= screen.bottom():
      new_y = screen.bottom() - self.height()
      self.vy = -abs(self.vy)

    # Commit coordinates to window
    self.move(new_x, new_y)


if __name__ == "__main__":
  app = QApplication(sys.argv)
  # Replace 'pet.png' with your character image file
  pet = DesktopPet(sprite_path="pet.png")
  pet.show()
  sys.exit(app.exec())
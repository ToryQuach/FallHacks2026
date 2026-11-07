import sys
import threading
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

# Import your existing bubble builder
from chatbox import ChatBubbleBuilder


class ChatBubbleWindow(QWidget):
  # Thread-safe signal to push text updates from the CLI thread to Qt's GUI thread
  update_text_signal = pyqtSignal(str)

  def __init__(self, builder: ChatBubbleBuilder, initial_text: str = "Ready!"):
    super().__init__()
    self.builder = builder

    # 1. Window Flags: Frameless, stays on top, hidden from Alt-Tab taskbar
    self.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )

    # 2. Transparent background: Transparent alpha pixels pass mouse events straight through
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # State variables for dragging
    self.is_dragging = False
    self.drag_offset = QPoint()
    self.pixmap = QPixmap()

    # Connect signal to update method
    self.update_text_signal.connect(self.set_bubble_text)

    # Render initial bubble
    self.set_bubble_text(initial_text)

    # Center window initially on primary monitor
    screen = QApplication.primaryScreen().availableGeometry()
    self.move(
        (screen.width() - self.width()) // 2,
        (screen.height() - self.height()) // 2,
    )

  def set_bubble_text(self, text: str):
    """Constructs bubble in-memory via PIL and updates the Qt texture."""
    pil_image = self.builder.constructChatbox(text)

    # Convert PIL Image to QPixmap directly in memory (zero disk I/O)
    q_img = ImageQt(pil_image)
    self.pixmap = QPixmap.fromImage(q_img)

    # Resize window to exactly match the new bubble's bounds
    self.resize(self.pixmap.size())
    self.update()

  def paintEvent(self, event):
    if not self.pixmap.isNull():
      painter = QPainter(self)
      painter.drawPixmap(0, 0, self.pixmap)

  # --- Drag Handling (Applies only when clicking solid/semi-opaque bubble pixels) ---
  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.is_dragging = True
      self.drag_offset = (
          event.globalPosition().toPoint() - self.frameGeometry().topLeft()
      )
      event.accept()

  def mouseMoveEvent(self, event):
    if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
      self.move(event.globalPosition().toPoint() - self.drag_offset)
      event.accept()

  def mouseReleaseEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.is_dragging = False
      event.accept()


# ---------------- Background CLI Console Loop ----------------
def cli_input_thread(window: ChatBubbleWindow):
  print("\n" + "=" * 50)
  print(" PyQt6 Live Chatbox Overlay (In-Memory)")
  print("=" * 50)
  print("Overlay is live! Transparent background passes clicks through.")
  print("Click & drag the speech bubble to reposition it.\n")
  print("Type text and hit [Enter] to update. Type 'exit' to quit.\n")

  while True:
    try:
      text = input("Bubble text > ").strip()
      if not text:
        continue
      if text.lower() in ("exit", "quit", "q"):
        print("Closing overlay...")
        QApplication.quit()
        break

      # Safely emit signal to the GUI thread
      window.update_text_signal.emit(text)

    except (KeyboardInterrupt, EOFError):
      QApplication.quit()
      break


# ---------------- Entrypoint ----------------
def main():
  app = QApplication(sys.argv)

  # Initialize your 9-slice builder
  builder = ChatBubbleBuilder(
      slices_dir="chat_bubble_kit/cream/slices",
      font_size=15,
      text_color=(20, 20, 20),
      max_text_width=240,
  )

  # Create and show window
  window = ChatBubbleWindow(
      builder, initial_text="I'm your new digital sidekick!"
  )
  window.show()

  # Start console listener in background thread
  t = threading.Thread(target=cli_input_thread, args=(window,), daemon=True)
  t.start()

  sys.exit(app.exec())


if __name__ == "__main__":
  main()
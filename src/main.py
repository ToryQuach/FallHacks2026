import os
import queue
import sys
import threading

# Add src and subdirectories to sys.path
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([
    _SRC_DIR,
    os.path.join(_SRC_DIR, "display"),
    os.path.join(_SRC_DIR, "gemini"),
    os.path.join(_SRC_DIR, "menu"),
])

from display import MascotDisplay
from menu import menu
from pipeline import run_gemini_pipeline


def main():
  # 1. Launch Setup Menu (Runs PyQt QDialog)
  print("[Main] Launching configuration menu...")
  config = menu()

  if not config:
    print("[Main] Setup cancelled by user. Exiting.")
    return 0

  print("[Main] Config selected:")
  print(f"  - Personality : {config['personality'].get('name')}")
  print(f"  - Goal        : {config['goal']}")
  print(f"  - Duration    : {config['duration_hms']}")
  print(f"  - Interval    : {config['check_interval_seconds']}s")
  print(f"  - Sprites     : {config['sprite_folder']}")

  # Thread-safe queue for user interaction submitted through the mascot window
  user_input_queue = queue.Queue()
  stop_event = threading.Event()

  def handle_submit(text: str):
    print(f"[Main] User replied to mascot: {text}")
    user_input_queue.put(text)

  # 2. Initialize Mascot Display Window (using default sprites)
  display_app = MascotDisplay(onSubmit=handle_submit)

  # Bridge callback from Gemini thread into MascotDisplay's PyQt signal
  def on_sidekick_speak(text: str, reaction: str):
    display_app.ai_response_signal.emit(text, reaction)

  # 3. Spawn Gemini pipeline in background daemon thread
  pipeline_thread = threading.Thread(
      target=run_gemini_pipeline,
      args=(config, on_sidekick_speak, user_input_queue, stop_event),
      daemon=True,
  )
  pipeline_thread.start()

  # 4. Start GUI event loop on main thread
  try:
    exit_code = display_app.run()
  finally:
    # Graceful shutdown of pipeline thread on exit
    stop_event.set()
    pipeline_thread.join(timeout=1.0)

  return exit_code


if __name__ == "__main__":
  sys.exit(main())
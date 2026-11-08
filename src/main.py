import os
import queue
import sys
import threading

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([
    _SRC_DIR,
    os.path.join(_SRC_DIR, "display"),
    os.path.join(_SRC_DIR, "gemini"),
    os.path.join(_SRC_DIR, "menu"),
    os.path.join(_SRC_DIR, "tts"),
])

from display import MascotDisplay
from menu import menu
from pipeline import run_gemini_pipeline
import tts

# Read the sidekick's lines aloud
TTS_ENABLED = True


def main():
  print("[Main] Launching configuration menu...")
  config = menu()
  if not config:
    print("[Main] Setup cancelled.")
    return 0

  user_input_queue = queue.Queue()
  force_speak_event = threading.Event()
  stop_event = threading.Event()

  def handle_submit(text: str):
    print(f"[Main] User replied: {text}")
    user_input_queue.put(text)

  def handle_poke():
    print("[Main] Poke button clicked -> Forcing Gemini speech!")
    force_speak_event.set()

  # Pass onPoke callback to MascotDisplay
  display_app = MascotDisplay(onSubmit=handle_submit, onPoke=handle_poke)

  if TTS_ENABLED:
    tts.warm_up()

  def on_sidekick_speak(text: str, reaction: str):
    display_app.ai_response_signal.emit(text, reaction)
    if TTS_ENABLED:
      tts.speak(text, config.get("personality"))

  pipeline_thread = threading.Thread(
      target=run_gemini_pipeline,
      args=(
          config,
          on_sidekick_speak,
          user_input_queue,
          force_speak_event,
          stop_event,
          display_app.isInputActive,
      ),
      daemon=True,
  )
  pipeline_thread.start()

  try:
    exit_code = display_app.run()
  finally:
    stop_event.set()
    pipeline_thread.join(timeout=1.0)

  return exit_code


if __name__ == "__main__":
  sys.exit(main())
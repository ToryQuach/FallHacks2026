"""pipeline.py - Core background loop for digital sidekick observation and reaction."""

from datetime import datetime
import queue
import random
import threading
import time
from typing import Callable, Optional
from gemini import (
    HistoryQueue,
    capture_screenshot,
    get_observation,
    get_sidekick_response,
)
from pynput import keyboard

# Default Timing Fallbacks
DEFAULT_OBSERVE_SECONDS = 20
DEFAULT_SPEAK_MIN_SECONDS = 40
DEFAULT_SPEAK_MAX_SECONDS = 60

# Hotkey to trigger speech on demand
SPEAK_HOTKEY = "<ctrl>+<alt>+s"

MEMORY_SIZE = 30


def run_gemini_pipeline(
    config: dict,
    on_sidekick_speak: Callable[[str, str], None],
    user_input_queue: queue.Queue,
    stop_event: threading.Event,
):
  """Runs the observation and speech loop in a background thread."""
  # 1. Observation / Check Interval from menu config or fallback
  observe_interval = config.get(
      "check_interval_seconds", DEFAULT_OBSERVE_SECONDS
  )

  # 2. Speaking Interval bounds
  speak_min = config.get("speak_min_seconds", DEFAULT_SPEAK_MIN_SECONDS)
  speak_max = config.get("speak_max_seconds", DEFAULT_SPEAK_MAX_SECONDS)

  goals = config.get("goal", "General Productivity")
  personality = config.get("personality", {})
  session_duration = config.get("duration_seconds", 0)

  start_monotonic = time.monotonic()

  # Event triggered by keybind or user chat
  force_speak_event = threading.Event()

  def trigger_immediate_speech():
    print(f"\n[Hotkey] '{SPEAK_HOTKEY}' pressed -> Triggering immediate speech!")
    force_speak_event.set()

  # Register global hotkey listener
  hotkey_listener = keyboard.GlobalHotKeys({
      SPEAK_HOTKEY: trigger_immediate_speech,
  })
  hotkey_listener.daemon = True
  hotkey_listener.start()

  def next_response_time() -> float:
    return time.monotonic() + random.uniform(speak_min, speak_max)

  with HistoryQueue(max_size=MEMORY_SIZE) as history:
    print(f"[Gemini Worker] Active. Persona: {personality.get('name', 'Default')}")
    print(f"[Gemini Worker] Press {SPEAK_HOTKEY} at any time to force speech.")
    respond_at = next_response_time()
    last_obs = None

    while not stop_event.is_set():
      loop_start = time.monotonic()
      timestamp = datetime.now().strftime("%H:%M:%S")

      # Check session timeout
      if (
          session_duration > 0
          and (time.monotonic() - start_monotonic) >= session_duration
      ):
        on_sidekick_speak(
            "Session complete! Time's up for today's goal.", "happiness"
        )
        break

      try:
        # Check if user submitted text from GUI chat bubble
        has_user_reply = False
        while not user_input_queue.empty():
          user_text = user_input_queue.get_nowait()
          history.append(
              timestamp,
              f"User said to you: {user_text}",
              metadata={"source": "user_chat"},
          )
          has_user_reply = True

        # If user spoke to mascot, trigger reply immediately
        if has_user_reply:
          force_speak_event.set()

        # 1. Observe Screen
        obs = get_observation(
            image_path=capture_screenshot(),
            mouse_active=True,
            current_timestamp=timestamp,
            history_queue=history,
            goals=goals,
        )
        last_obs = obs
        print(f"[{timestamp}] observe: {obs.status_classification} - {obs.summary}")

        # 2. Check if we should speak (Timer elapsed OR forced by hotkey / user chat)
        timer_due = time.monotonic() >= respond_at
        forced = force_speak_event.is_set()

        if timer_due or forced:
          force_speak_event.clear()

          reply = get_sidekick_response(
              observation=obs,
              current_timestamp=timestamp,
              history_queue=history,
              personality=personality,
              goals=goals,
          )

          print(f"[{timestamp}] SPEAK [{reply.reaction}]: {reply.bubble_speech}")

          # Push to display
          on_sidekick_speak(reply.bubble_speech, reply.reaction)
          respond_at = next_response_time()

      except Exception as e:
        print(f"[{timestamp}] API failed: {e}")

      # Respect observation interval or break early if forced/stopped
      elapsed = time.monotonic() - loop_start
      remaining_sleep = max(0.1, observe_interval - elapsed)

      # Wait in short slices so hotkeys trigger promptly without lagging the loop
      slice_time = 0.2
      slept = 0.0
      while slept < remaining_sleep and not stop_event.is_set():
        if force_speak_event.is_set():
          break
        time.sleep(slice_time)
        slept += slice_time

    hotkey_listener.stop()
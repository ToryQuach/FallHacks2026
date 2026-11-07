"""
pipeline.py - Core background loop for digital sidekick observation, conversation, and reaction.
"""

from datetime import datetime
import queue
import random
import threading
import time
from typing import Callable, Optional

from pydantic import BaseModel

from gemini import (
    HistoryQueue,
    capture_screenshot,
    get_observation,
    get_sidekick_response,
)

DEFAULT_OBSERVE_SECONDS = 20
DEFAULT_SPEAK_MIN_SECONDS = 6
DEFAULT_SPEAK_MAX_SECONDS = 7
MEMORY_SIZE = 30


class DirectChatObservation(BaseModel):
  summary: str
  status_classification: str = "DIRECT_CONVERSATION"
  reasoning: Optional[str] = "User addressed the sidekick directly."
  model_config = {"extra": "allow"}


def run_gemini_pipeline(
    config: dict,
    on_sidekick_speak: Callable[[str, str], None],
    user_input_queue: queue.Queue,
    force_speak_event: threading.Event,
    stop_event: threading.Event,
    is_input_active: Optional[Callable[[], bool]] = None,
):
  observe_interval = config.get(
      "check_interval_seconds", DEFAULT_OBSERVE_SECONDS
  )
  speak_min = config.get("speak_min_seconds", DEFAULT_SPEAK_MIN_SECONDS)
  speak_max = config.get("speak_max_seconds", DEFAULT_SPEAK_MAX_SECONDS)

  goals = config.get("goal", "General Productivity")
  personality = config.get("personality", {})
  session_duration = config.get("duration_seconds", 0)

  start_monotonic = time.monotonic()

  def next_response_time() -> float:
    return time.monotonic() + random.uniform(speak_min, speak_max)

  with HistoryQueue(max_size=MEMORY_SIZE) as history:
    print(
        f"[Gemini Worker] Active. Persona: {personality.get('name', 'Default')}"
    )
    respond_at = next_response_time()
    last_obs = None
    last_observe_time = 0.0

    while not stop_event.is_set():
      timestamp = datetime.now().strftime("%H:%M:%S")

      if (
          session_duration > 0
          and (time.monotonic() - start_monotonic) >= session_duration
      ):
        on_sidekick_speak(
            "Session complete! Time's up for today's goal.", "happiness"
        )
        break

      try:
        # 1. User Direct Chat
        if not user_input_queue.empty():
          user_text = user_input_queue.get_nowait()
          print(
              f"[{timestamp}] DIRECT CHAT -> Prompting Gemini with: {user_text}"
          )

          history.append(
              timestamp,
              f"User directly said to you: '{user_text}'",
              metadata={"source": "user_chat"},
          )

          chat_obs = DirectChatObservation(
              summary=(
                  f"The user typed directly to you: '{user_text}'. Respond"
                  " directly to what they said in character."
              )
          )

          chat_reply = get_sidekick_response(
              observation=chat_obs,
              current_timestamp=timestamp,
              history_queue=history,
              personality=personality,
              goals=goals,
          )

          print(
              f"[{timestamp}] DIRECT REPLY [{chat_reply.reaction}]:"
              f" {chat_reply.bubble_speech}"
          )
          on_sidekick_speak(chat_reply.bubble_speech, chat_reply.reaction)
          respond_at = next_response_time()
          continue

        # 2. Screen observation (interval or poke button)
        now = time.monotonic()
        forced = force_speak_event.is_set()

        if forced or (now - last_observe_time >= observe_interval):
          last_observe_time = now
          obs = get_observation(
              image_path=capture_screenshot(),
              mouse_active=True,
              current_timestamp=timestamp,
              history_queue=history,
              goals=goals,
          )
          last_obs = obs
          print(
              f"[{timestamp}] observe: {obs.status_classification} -"
              f" {obs.summary}"
          )

        # 3. Speak (timer reached OR Poke button was clicked)
        timer_due = time.monotonic() >= respond_at

        # Check if user is currently typing in the scroll box
        typing_in_progress = is_input_active() if is_input_active else False

        # If it's just the automatic timer and the user is typing, defer speech
        if timer_due and not forced and typing_in_progress:
          # Postpone speaking by 3 seconds so we don't interrupt typing
          respond_at = time.monotonic() + 3.0
          timer_due = False

        if (forced or timer_due) and last_obs is not None:
          force_speak_event.clear()

          reply = get_sidekick_response(
              observation=last_obs,
              current_timestamp=timestamp,
              history_queue=history,
              personality=personality,
              goals=goals,
          )

          print(
              f"[{timestamp}] SPOKE [{reply.reaction}]: {reply.bubble_speech}"
          )
          on_sidekick_speak(reply.bubble_speech, reply.reaction)
          respond_at = next_response_time()

      except Exception as e:
        print(f"[{timestamp}] Pipeline error: {e}")

      for _ in range(5):
        if (
            stop_event.is_set()
            or not user_input_queue.empty()
            or force_speak_event.is_set()
        ):
          break
        time.sleep(0.05)
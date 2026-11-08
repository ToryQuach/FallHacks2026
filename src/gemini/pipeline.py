"""
pipeline.py - Main loop for the desktop sidekick.

Two things happen on different timers:
  1. OBSERVE (every 20s): take a screenshot and ask Gemini what the user is
     doing. The one-line summary is saved to the history queue.
  2. SPEAK (randomly every 50-70s): ask Gemini, in character, how the sidekick
     reacts to the latest observation. This is what the sprite says.

Run from the project root:
    python src/gemini/pipeline.py
"""

import random
import sys
import time
from datetime import datetime
from pathlib import Path

# Let Python find src/tts/tts.py (same trick gemini.py uses for history)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tts"))
import tts  # noqa: E402

TTS_ENABLED = True


from gemini import (
    HistoryQueue,
    capture_screenshot,
    get_observation,
    get_sidekick_response,
    load_goals,
    load_personality,
)

# Timing
# Observation timing
OBSERVE_SECONDS = 5
# Response timing
RESPOND_MIN_SECONDS = 20      
RESPOND_MAX_SECONDS = 30      

# Memory size
MEMORY_SIZE = 30


def next_response_time() -> float:
   return time.monotonic() + random.uniform(RESPOND_MIN_SECONDS, RESPOND_MAX_SECONDS)


def main():
    # Read goal.txt and personality.txt once at startup.
    # Restart the script after editing them
    goals = load_goals()
    personality = load_personality()

    # `with` clears the history when the loop exits
    with HistoryQueue(max_size=MEMORY_SIZE) as history:
        print("Sidekick running. Press Ctrl+C to stop.")
        respond_at = next_response_time()

        while True:
            loop_start = time.monotonic()
            timestamp = datetime.now().strftime("%H:%M:%S")

            try:
                # 1. Observe: screenshot -> context for response
                # appends obs.summary to history
                obs = get_observation(
                    image_path=capture_screenshot(),
                    mouse_active=True,
                    current_timestamp=timestamp,
                    history_queue=history,
                    goals=goals,
                )
                print(f"[{timestamp}] observe: {obs.status_classification} - {obs.summary}")

                # 2. SPEAK: only once the random 50-70s timer is up.
                #    Text-only call (no image), so it's cheaper than observing.
                if time.monotonic() >= respond_at:
                    reply = get_sidekick_response(
                        observation=obs,
                        current_timestamp=timestamp,
                        history_queue=history,
                        personality=personality,
                        goals=goals,
                    )
                    # TODO: send reply.reaction / reply.bubble_speech to src/display
                    print(f"[{timestamp}] SPEAK {reply.reaction}: {reply.bubble_speech}")
                    if TTS_ENABLED:
                        
                        tts.speak(reply.bubble_speech, personality)
                    respond_at = next_response_time()

            except Exception as e:
                # Don't crash the loop on a bad API call; try again next round
                print(f"[{timestamp}] API failed: {e}")

            # Sleep for whatever is left of the 20s, so slow API calls
            # don't push the schedule back
            elapsed = time.monotonic() - loop_start
            time.sleep(max(0, OBSERVE_SECONDS - elapsed))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")

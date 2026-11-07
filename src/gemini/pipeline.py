import random
import time
from datetime import datetime

from gemini import (
    HistoryQueue,
    capture_screenshot,
    get_observation,
    get_sidekick_response,
    load_goals,
    load_personality,
)

OBSERVE_SECONDS = 20          # how often to look at the screen
RESPOND_MIN_SECONDS = 50      # sidekick speaks at a random time
RESPOND_MAX_SECONDS = 70      # between these two values
MEMORY_SIZE = 10              # how many past summaries the model remembers


def next_response_time() -> float:
    return time.monotonic() + random.uniform(RESPOND_MIN_SECONDS, RESPOND_MAX_SECONDS)


def main():
    # Read the text files once at startup
    goals = load_goals()
    personality = load_personality()

    with HistoryQueue(max_size=MEMORY_SIZE) as history:
        print("Sidekick running. Press Ctrl+C to stop.")
        respond_at = next_response_time()

        while True:
            loop_start = time.monotonic()
            timestamp = datetime.now().strftime("%H:%M:%S")

            try:
                # Every loop: what is the user doing? (adds obs.summary to history)
                obs = get_observation(
                    image_path=capture_screenshot(),
                    mouse_active=True,  # TODO: hook up real input tracking from src/input
                    current_timestamp=timestamp,
                    history_queue=history,
                    goals=goals,
                )
                print(f"[{timestamp}] observe: {obs.status_classification} - {obs.summary}")

                # Every 50-70s: the sidekick reacts to the latest observation
                if time.monotonic() >= respond_at:
                    reply = get_sidekick_response(
                        observation=obs,
                        current_timestamp=timestamp,
                        history_queue=history,
                        personality=personality,
                        goals=goals,
                    )
                    print(f"[{timestamp}] SPEAK {reply.reaction}: {reply.bubble_speech}")
                    respond_at = next_response_time()
            except Exception as e:
                print(f"[{timestamp}] API failed: {e}")

            # Sleep the rest of the 20s so API time doesn't stretch the interval
            time.sleep(max(0, OBSERVE_SECONDS - (time.monotonic() - loop_start)))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")

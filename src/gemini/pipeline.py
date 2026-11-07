import time
from collections import deque
from datetime import datetime
from dotenv import load_dotenv

from gemini import (
    capture_screenshot,
    get_sidekick_response,
    load_system_instruction,
)

LOOP_SECONDS = 10    # how often to check the screen
MEMORY_SIZE = 10     # how many past summaries the model remembers


def main():
    # Build the prompt once at startup (re-call this if personality/goals change)
    system_instruction = load_system_instruction()
    memory = deque(maxlen=MEMORY_SIZE)

    print("Sidekick running. Press Ctrl+C to stop.")
    while True:
        image_path = capture_screenshot()
        timestamp = datetime.now().strftime("%H:%M:%S")

        try:
            result = get_sidekick_response(
                image_path=image_path,
                mouse_active=True,  # TODO: hook up real input tracking from src/input
                current_timestamp=timestamp,
                memory_queue=list(memory),
                system_instruction=system_instruction,
            )
        except RuntimeError as e:
            print(f"[{timestamp}] API failed: {e}")
        else:
            memory.append(f"[{timestamp}] {result.session_summary_entry}")
            print(f"[{timestamp}] {result.status_classification} / {result.reaction}: {result.bubble_speech}")

        time.sleep(LOOP_SECONDS)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")


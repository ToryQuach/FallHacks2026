import time
from datetime import datetime

from gemini import (
    HistoryQueue,
    capture_screenshot,
    get_sidekick_response,
    load_system_instruction,
)

LOOP_SECONDS = 10    # how often to check the screen
MEMORY_SIZE = 10     # how many past summaries the model remembers


def main():
    # Build the prompt once at startup (re-call this if personality/goals change)
    system_instruction = load_system_instruction()

    with HistoryQueue(max_size=MEMORY_SIZE) as history:
        print("Sidekick running. Press Ctrl+C to stop.")
        while True:
            image_path = capture_screenshot()
            timestamp = datetime.now().strftime("%H:%M:%S")

            try:
                # Also appends result.session_summary_entry to history
                result = get_sidekick_response(
                    image_path=image_path,
                    mouse_active=True,  # TODO: hook up real input tracking from src/input
                    current_timestamp=timestamp,
                    history_queue=history,
                    system_instruction=system_instruction,
                )
            except RuntimeError as e:
                print(f"[{timestamp}] API failed: {e}")
            else:
                print(f"[{timestamp}] {result.status_classification} / {result.reaction}: {result.bubble_speech}; {result.detected_activities}")
                print(f"  History ({len(history)}/{MEMORY_SIZE}):")
                for line in history.to_list():
                    print(f"    {line}")

            time.sleep(LOOP_SECONDS)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")

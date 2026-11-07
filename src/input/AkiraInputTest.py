import threading
import time
from pynput import mouse

# Configuration
TIMEOUT_SECONDS = 8
STATUS_INTERVAL = 3

# Shared state
timer = float(TIMEOUT_SECONDS)
focused = True
lock = threading.Lock()
running = True


def on_move(x, y):
    """Callback triggered whenever the mouse moves."""
    global timer, focused
    with lock:
        timer = float(TIMEOUT_SECONDS)
        focused = True


def countdown_worker():
    """Background worker that decrements the timer every 0.1s."""
    global timer, focused, running
    while running:
        time.sleep(0.1)
        with lock:
            if timer > 0:
                timer = max(0.0, timer - 0.1)
                if timer == 0:
                    focused = False


# Start the pynput mouse listener thread
listener = mouse.Listener(on_move=on_move)
listener.daemon = True
listener.start()

# Start the countdown timer thread
timer_thread = threading.Thread(target=countdown_worker, daemon=True)
timer_thread.start()

# Main loop: reports status every ~3 seconds
try:
    while True:
        time.sleep(STATUS_INTERVAL)
        with lock:
            current_focus = focused
            remaining_time = timer

        print(f"Focused: {current_focus} | Time Remaining: {remaining_time:.1f}s")

except KeyboardInterrupt:
    running = False
    print("\nStopped.")
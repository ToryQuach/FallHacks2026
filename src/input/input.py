import pyautogui
import time

def track_mouse_position():
    while True:

        #mouse position
        x, y = pyautogui.position()
        time.sleep(1)

track_mouse_position()



import time

def timer(seconds):
    while seconds:
        try:
            mins, secs = divmod(seconds, 60)
            timeformat = '{:02d}:{:02d}'.format(mins, secs)
            print(timeformat, end='\r')
            time.sleep(1)
            seconds -= 1
        except KeyboardInterrupt:
            print("\n Process terminated by user")
            return 0
    print('00:00', end='\r')

timer(500)
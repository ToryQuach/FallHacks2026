import os

class ImagePathIterator:
    def __init__(self, path, start):
        self.path = path
        self.currentFrame = start
        self.maxFrame = len(os.listdir(self.path))

    def __iter__(self):
        return self
    
    def __next__(self):
        path = os.path.join(self.path, f"frame_{self.currentFrame}")

        self.currentFrame = (self.currentFrame + 1) % self.maxFrame
        
        return path

    def setFrame(self, frame):
        self.currentFrame = frame
from utils import ImagePathIterator
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

class Mascot:
    DEFAULT_SPRITE_PATH        = os.path.join(_HERE, "resources", "sprites", "default")
    ANGER_SPRITE_PATH          = os.path.join(_HERE, "resources", "sprites", "anger")
    ANNOYANCE_SPRITE_PATH      = os.path.join(_HERE, "resources", "sprites", "annoyance")
    DISAPPOINTMENT_SPRITE_PATH = os.path.join(_HERE, "resources", "sprites", "disappointment")
    EXCITEMENT_SPRITE_PATH     = os.path.join(_HERE, "resources", "sprites", "excitement")
    HAPPINESS_SPRITE_PATH      = os.path.join(_HERE, "resources", "sprites", "happiness")
    SCROLL_SPRITE_PATH         = os.path.join(_HERE, "resources", "sprites", "scroll")

    DEFAULT        = 0
    ANGER          = 1
    ANNOYANCE      = 2
    DISAPPOINTMENT = 3
    EXCITEMENT     = 4
    HAPPINESS      = 5
    SCROLL         = 6

    def __init__(self):
        self.sprites = {
            self.DEFAULT:        ImagePathIterator(self.DEFAULT_SPRITE_PATH, 0),
            self.ANGER:          ImagePathIterator(self.ANGER_SPRITE_PATH, 0),
            self.ANNOYANCE:      ImagePathIterator(self.ANNOYANCE_SPRITE_PATH, 0),
            self.DISAPPOINTMENT: ImagePathIterator(self.DISAPPOINTMENT_SPRITE_PATH, 0),
            self.EXCITEMENT:     ImagePathIterator(self.EXCITEMENT_SPRITE_PATH, 0),
            self.HAPPINESS:      ImagePathIterator(self.HAPPINESS_SPRITE_PATH, 0),
            self.SCROLL:         ImagePathIterator(self.SCROLL_SPRITE_PATH, 0)
        }
        self.currState = self.DEFAULT

    # Setters
    def setState(self, state):
        self.currState = state
        self.setCurStateFrame(0)

    def setCurStateFrame(self, frame):
        self.getCurSpriteIterator().setFrame(frame)

    # Getters
    def getState(self):
        return self.currState

    def getCurSpriteIterator(self):
        return self.sprites[self.currState]

    def getNextImage(self):
        return self.getCurSpriteIterator().__next__()
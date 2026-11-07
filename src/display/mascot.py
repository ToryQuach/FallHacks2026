from utils import ImagePathIterator
import os

class Mascot:
    DEFAULT_SPRITE_PATH        = "./resources/sprites/default"
    ANGER_SPRITE_PATH          = "./resources/sprites/anger"
    ANNOYANCE_SPRITE_PATH      = "./resources/sprites/annoyance"
    DISAPPOINTMENT_SPRITE_PATH = "./resources/sprites/disappointment"
    EXCITEMENT_SPRITE_PATH     = "./resources/sprites/excitement"
    HAPPINESS_SPRITE_PATH      = "./resources/sprites/happiness"

    DEFAULT        = 0
    ANGER          = 1
    ANNOYANCE      = 2
    DISAPPOINTMENT = 3
    EXCITEMENT     = 4
    HAPPINESS      = 5

    def __init__(self):
        self.sprites = {
            self.DEFAULT:        ImagePathIterator(self.DEFAULT_SPRITE_PATH, 0),
            self.ANGER:          ImagePathIterator(self.ANGER_SPRITE_PATH, 0),
            self.ANNOYANCE:      ImagePathIterator(self.ANNOYANCE_SPRITE_PATH, 0),
            self.DISAPPOINTMENT: ImagePathIterator(self.DISAPPOINTMENT_SPRITE_PATH, 0),
            self.EXCITEMENT:     ImagePathIterator(self.EXCITEMENT_SPRITE_PATH, 0),
            self.HAPPINESS:      ImagePathIterator(self.HAPPINESS_SPRITE_PATH, 0)
        }
        self.currState = self.DEFAULT

    def setState(self, state):
        self.currState = state
        

    def getState(self):
        return self.currState

    def getNextImage(self):
        pass
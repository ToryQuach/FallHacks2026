import os
from utils import ImagePathIterator
from PyQt6.QtCore import pyqtSignal

_HERE = os.path.dirname(os.path.abspath(__file__))


class Mascot:
  DEFAULT_SPRITE_PATH = os.path.join(_HERE, "resources", "sprites", "default")
  ANGER_SPRITE_PATH = os.path.join(_HERE, "resources", "sprites", "anger")
  ANNOYANCE_SPRITE_PATH = os.path.join(
      _HERE, "resources", "sprites", "annoyance"
  )
  DISAPPOINTMENT_SPRITE_PATH = os.path.join(
      _HERE, "resources", "sprites", "disappointment"
  )
  EXCITEMENT_SPRITE_PATH = os.path.join(
      _HERE, "resources", "sprites", "excitement"
  )
  HAPPINESS_SPRITE_PATH = os.path.join(
      _HERE, "resources", "sprites", "happiness"
  )
  SCROLL_SPRITE_PATH = os.path.join(_HERE, "resources", "sprites", "scroll")

  DEFAULT = 0
  ANGER = 1
  ANNOYANCE = 2
  DISAPPOINTMENT = 3
  EXCITEMENT = 4
  HAPPINESS = 5
  SCROLL = 6

  # String mapping from Gemini reactions
  REACTION_MAP = {
      "default": DEFAULT,
      "neutral": DEFAULT,
      "anger": ANGER,
      "angry": ANGER,
      "annoyance": ANNOYANCE,
      "annoyed": ANNOYANCE,
      "disappointment": DISAPPOINTMENT,
      "disappointed": DISAPPOINTMENT,
      "excitement": EXCITEMENT,
      "excited": EXCITEMENT,
      "happiness": HAPPINESS,
      "happy": HAPPINESS,
      "scroll": SCROLL,
  }

  def __init__(self, base_sprite_dir=None):
    # If a custom sprite folder was selected from menu, resolve states inside it
    root = (
        base_sprite_dir
        if base_sprite_dir and os.path.isdir(base_sprite_dir)
        else os.path.join(_HERE, "resources", "sprites")
    )

    def get_path(folder_name, fallback_path):
      custom_path = os.path.join(root, folder_name)
      return custom_path if os.path.isdir(custom_path) else fallback_path

    self.sprites = {
        self.DEFAULT: ImagePathIterator(
            get_path("default", self.DEFAULT_SPRITE_PATH), 0
        ),
        self.ANGER: ImagePathIterator(
            get_path("anger", self.ANGER_SPRITE_PATH), 0
        ),
        self.ANNOYANCE: ImagePathIterator(
            get_path("annoyance", self.ANNOYANCE_SPRITE_PATH), 0
        ),
        self.DISAPPOINTMENT: ImagePathIterator(
            get_path("disappointment", self.DISAPPOINTMENT_SPRITE_PATH), 0
        ),
        self.EXCITEMENT: ImagePathIterator(
            get_path("excitement", self.EXCITEMENT_SPRITE_PATH), 0
        ),
        self.HAPPINESS: ImagePathIterator(
            get_path("happiness", self.HAPPINESS_SPRITE_PATH), 0
        ),
        self.SCROLL: ImagePathIterator(
            get_path("scroll", self.SCROLL_SPRITE_PATH), 0
        ),
    }
    self.currState = self.DEFAULT

  def setState(self, state):
    if state in self.sprites:
      self.currState = state
      self.setCurStateFrame(0)

  def setReaction(self, reaction_name: str):
    """Translates Gemini reaction string to mascot animation state."""
    state = self.REACTION_MAP.get(str(reaction_name).lower(), self.DEFAULT)
    self.setState(state)

  def setCurStateFrame(self, frame):
    self.getCurSpriteIterator().setFrame(frame)

  def getState(self):
    return self.currState

  def getCurSpriteIterator(self):
    return self.sprites[self.currState]

  def getNextImage(self):
    return self.getCurSpriteIterator().__next__()
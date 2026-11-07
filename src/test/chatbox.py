import os
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


class ChatBubbleBuilder:
  """Builds dynamic 9-slice chat bubbles from modular slices, with an attached pointer tail."""

  SLICE_KEYS = ["tl", "t", "tr", "l", "c", "r", "bl", "b", "br"]

  def __init__(
      self,
      slices_dir: str = "chat_bubble_kit/crea/slices",
      tail_filename: str = "tail_left_cream.png",
      tail_offset_x: int = 24,
      font_path: Optional[str] = None,
      font_size: int = 16,
      text_color: Tuple[int, int, int] = (20, 20, 20),
      padding: Tuple[int, int] = (16, 12),
      max_text_width: int = 240,
  ):
    """Args:

    slices_dir: Directory containing the 9-slice PNGs.
    tail_filename: Filename of the pointer tail (searched in slices_dir, then
    parent dir).
    tail_offset_x: Pixels from the left border to position the tail.
    font_path: Path to custom .ttf/.otf (defaults to arial/system default).
    font_size: Point size for the text.
    text_color: RGB tuple for font rendering.
    padding: (horizontal_padding, vertical_padding) around text inside the
    bubble.
    max_text_width: Max width in pixels before wrapping text.
    """
    self.slices_dir = slices_dir
    self.tail_filename = tail_filename
    self.tail_offset_x = tail_offset_x
    self.padding_x, self.padding_y = padding
    self.text_color = text_color
    self.max_text_width = max_text_width

    # Load font
    if font_path and os.path.exists(font_path):
      self.font = ImageFont.truetype(font_path, font_size)
    else:
      try:
        self.font = ImageFont.truetype("arial.ttf", font_size)
      except IOError:
        self.font = ImageFont.load_default()

    # Preload assets into memory
    self.slices = self._load_slices()
    self.tail = self._load_tail()

  def _load_slices(self) -> dict:
    slices = {}
    for key in self.SLICE_KEYS:
      path = os.path.join(self.slices_dir, f"{key}.png")
      if not os.path.exists(path):
        raise FileNotFoundError(f"Missing required bubble slice: '{path}'")
      slices[key] = Image.open(path).convert("RGBA")
    return slices

  def _load_tail(self) -> Optional[Image.Image]:
    # Check in slices_dir first, then parent directory (e.g., chat_bubble_kit/crea)
    candidate_paths = [
        os.path.join(self.slices_dir, self.tail_filename),
        os.path.join(os.path.dirname(self.slices_dir), self.tail_filename),
        self.tail_filename,
    ]
    for path in candidate_paths:
      if os.path.exists(path):
        return Image.open(path).convert("RGBA")

    print(
        f"[Warning] Tail image '{self.tail_filename}' not found in candidate"
        f" paths: {candidate_paths}. Proceeding without tail."
    )
    return None

  def _wrap_text(self, text: str, draw: ImageDraw.ImageDraw) -> str:
    lines = []
    for paragraph in text.splitlines():
      words = paragraph.split(" ")
      current_line = []

      for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=self.font)
        line_w = bbox[2] - bbox[0]

        if line_w <= self.max_text_width:
          current_line.append(word)
        else:
          if current_line:
            lines.append(" ".join(current_line))
          current_line = [word]

      if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)

  def _get_text_dimensions(self, text: str) -> Tuple[int, int, str]:
    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy_img)

    wrapped_text = self._wrap_text(text, draw)
    bbox = draw.textbbox((0, 0), wrapped_text, font=self.font, spacing=4)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return max(w, 10), max(h, 10), wrapped_text

  def constructChatbox(self, text: str) -> Image.Image:
    """Constructs and returns a PIL Image containing the 9-sliced bubble, rendered text, and attached pointer tail."""
    # 1. Measure text
    text_w, text_h, wrapped_text = self._get_text_dimensions(text)

    # 2. Slice dimensions
    s = self.slices
    w_l, _ = s["l"].size
    w_r, _ = s["r"].size
    _, h_t = s["t"].size
    _, h_b = s["b"].size

    # 3. Inner box dimensions
    target_inner_w = text_w + (self.padding_x * 2)
    target_inner_h = text_h + (self.padding_y * 2)

    center_w = max(s["c"].width, target_inner_w)
    center_h = max(s["c"].height, target_inner_h)

    box_w = w_l + center_w + w_r
    box_h = h_t + center_h + h_b

    # 4. Tail accommodation
    tail_w = self.tail.width if self.tail else 0
    tail_h = self.tail.height if self.tail else 0

    # The box must be at least wide enough to fit the tail with its offset
    if self.tail and (self.tail_offset_x + tail_w > box_w):
      extra_needed = (self.tail_offset_x + tail_w) - box_w
      center_w += extra_needed
      box_w = w_l + center_w + w_r

    # Canvas expands vertically by tail height (slight 1-2px overlap prevents rendering gaps)
    tail_overlap = 2 if self.tail else 0
    total_canvas_w = box_w
    total_canvas_h = box_h + max(0, tail_h - tail_overlap)

    canvas = Image.new("RGBA", (total_canvas_w, total_canvas_h), (0, 0, 0, 0))

    # 5. Scale stretching segments
    t_scaled = s["t"].resize(
        (center_w, h_t), resample=Image.Resampling.BILINEAR
    )
    b_scaled = s["b"].resize(
        (center_w, h_b), resample=Image.Resampling.BILINEAR
    )
    l_scaled = s["l"].resize(
        (w_l, center_h), resample=Image.Resampling.BILINEAR
    )
    r_scaled = s["r"].resize(
        (w_r, center_h), resample=Image.Resampling.BILINEAR
    )
    c_scaled = s["c"].resize(
        (center_w, center_h), resample=Image.Resampling.BILINEAR
    )

    # 6. Paste 9-slice segments
    # Top
    canvas.paste(s["tl"], (0, 0), s["tl"])
    canvas.paste(t_scaled, (w_l, 0), t_scaled)
    canvas.paste(s["tr"], (w_l + center_w, 0), s["tr"])

    # Middle
    canvas.paste(l_scaled, (0, h_t), l_scaled)
    canvas.paste(c_scaled, (w_l, h_t), c_scaled)
    canvas.paste(r_scaled, (w_l + center_w, h_t), r_scaled)

    # Bottom
    canvas.paste(s["bl"], (0, h_t + center_h), s["bl"])
    canvas.paste(b_scaled, (w_l, h_t + center_h), b_scaled)
    canvas.paste(s["br"], (w_l + center_w, h_t + center_h), s["br"])

    # 7. Paste Tail at bottom edge
    if self.tail:
      tail_x = self.tail_offset_x
      tail_y = box_h - tail_overlap
      canvas.paste(self.tail, (tail_x, tail_y), self.tail)

    # 8. Render wrapped text inside the bubble core
    draw = ImageDraw.Draw(canvas)
    text_x = w_l + (center_w - text_w) // 2
    text_y = h_t + (center_h - text_h) // 2

    draw.text(
        (text_x, text_y),
        wrapped_text,
        font=self.font,
        fill=self.text_color,
        spacing=4,
    )

    return canvas
import io
import json
import os
import time
from pathlib import Path
from typing import List, Literal, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from PIL import Image, ImageGrab
from pydantic import BaseModel, Field

from history import HistoryQueue

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

# gemini-3.5-flash-lite offers fast inference and high availability
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODEL = "gemini-3.8-flash"

# src/history holds personality.txt, goal.txt and the screenshot
HISTORY_DIR = Path(__file__).resolve().parent.parent / "history"
SCREENSHOT_PATH = HISTORY_DIR / "temp_screen.png"

DEFAULT_PERSONALITY = "You are a witty, mildly sarcastic digital desktop sidekick. Keep comments concise and sharp."
DEFAULT_GOALS = "Focus on programming, debugging, and reading documentation. Avoid social media, videos, and games."

_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    """Create the Gemini client on first use and reuse it after that."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file or environment.")
        _client = genai.Client(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class SidekickResponse(BaseModel):
    status_classification: Literal["FOCUSING", "STRUGGLING", "DISTRACTED", "CELEBRATING"] = Field(
        description="Assessment of whether the user is on-task, stuck, or distracted."
    )
    detected_activities: List[str] = Field(
        description="Key apps, open tabs, or document titles observed on screen."
    )
    reaction: Literal[
        "idle", "happy", "proud", "annoyed", "angry", "disappointed", "studying", "kick_screen"
    ] = Field(
        description="The emotional or animation reaction trigger for the desktop sprite."
    )
    bubble_speech: str = Field(
        description="Short, in-character line to display in the desktop speech bubble (max 35 words)."
    )
    session_summary_entry: str = Field(
        description="A 1-sentence chronological event summary to append to the rolling memory queue."
    )


# ---------------------------------------------------------------------------
# Persona and goals
# ---------------------------------------------------------------------------
def load_text_or_default(filepath: Path, default: str) -> str:
    path = Path(filepath)
    if path.is_file():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return content
    return default


def build_system_instruction(personality: str, goals: str) -> str:
    return f"""# SYSTEM INSTRUCTION: Autonomous Desktop Side-Kick Engine

## Persona
{personality}

Rules:
- Embody the persona directly without AI boilerplate or generic cheerleading.
- Keep `bubble_speech` under 35 words.

## Session Goals
{goals}

## Assessment Rules
- If idle/no input while stuck on an error trace or compiler output, status is STRUGGLING.
- If non-work media or games are active, status is DISTRACTED.
- If making steady progress or tests pass, status is FOCUSING or CELEBRATING.
"""


def load_system_instruction(history_dir: Path = HISTORY_DIR) -> str:
    """Read personality.txt and goal.txt (or use defaults) and build the prompt."""
    personality = load_text_or_default(history_dir / "personality.txt", DEFAULT_PERSONALITY)
    goals = load_text_or_default(history_dir / "goal.txt", DEFAULT_GOALS)
    return build_system_instruction(personality, goals)


# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------
def capture_screenshot(path: Path = SCREENSHOT_PATH) -> str:
    """Grab the screen and save it to `path`. On Wayland, or if capture fails,
    keep using the existing file at `path`."""
    # Pillow can't capture on Wayland, and its gnome-screenshot fallback hangs
    if os.getenv("XDG_SESSION_TYPE") == "wayland":
        if not Path(path).exists():
            raise RuntimeError(f"Can't capture the screen on Wayland and no screenshot at {path}")
        return str(path)
    try:
        ImageGrab.grab().save(path)
    except OSError:
        if not Path(path).exists():
            raise
    return str(path)


def get_optimized_image_bytes(image_path: str, max_dim: int = 1280) -> bytes:
    """Downscales and compresses screenshots to keep network latency under 200ms."""
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=True)
        return buf.getvalue()


# ---------------------------------------------------------------------------
<<<<<<< HEAD:src/gemini/gemini.py
# API call with retries
=======
# Step 4: Robust API Execution with History Integration
>>>>>>> 27e227614e68cab22ea20ef46ce65b20b7c367c6:src/history/gemini.py
# ---------------------------------------------------------------------------
def get_sidekick_response(
    image_path: str,
    mouse_active: bool,
    current_timestamp: str,
    history_queue: Optional[HistoryQueue] = None,
    user_message: Optional[str] = None,
    model_name: str = DEFAULT_MODEL,
    system_instruction: Optional[str] = None,
) -> SidekickResponse:
    if system_instruction is None:
        system_instruction = load_system_instruction()

    # 1. Compress screenshot
    image_bytes = get_optimized_image_bytes(image_path)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    # 2. Package telemetry via history_queue.form_json()
    rolling_history = history_queue.form_json() if history_queue else []
    state_payload = {
        "timestamp": current_timestamp,
        "mouse_active": mouse_active,
        "rolling_history": rolling_history,
        "user_direct_input": user_message or "None (Passive Monitoring)"
    }

    prompt_text = (
        f"Telemetry:\n```json\n{json.dumps(state_payload, indent=2)}\n```\n"
        "Evaluate the screenshot against session goals and respond via the schema."
    )

    # 3. Fast generation config
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=SidekickResponse,
        temperature=0.3,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )

    models_to_try = [model_name]
    if model_name != FALLBACK_MODEL:
        models_to_try.append(FALLBACK_MODEL)

    response = None
    last_err = None

    for target_model in models_to_try:
        for attempt in range(2):
            try:
                response = get_client().models.generate_content(
                    model=target_model,
                    contents=[prompt_text, image_part],
                    config=config,
                )
                break
            except errors.ServerError as e:
                last_err = e
                time.sleep(1.5)
            except Exception as e:
                last_err = e
                break

        if response is not None:
            break

    if response is None:
        raise RuntimeError(f"All model attempts failed with: {last_err}")

    # Parse Pydantic object
    if hasattr(response, "parsed") and isinstance(response.parsed, SidekickResponse):
        result_data = response.parsed
    else:
        raw_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        result_data = SidekickResponse.model_validate_json(raw_text)

    # 4. Append the response summary into history queue
    if history_queue is not None:
        history_queue.append(
            timestamp=current_timestamp,
            entry=result_data.session_summary_entry
        )

    return result_data


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    screenshot_path = "temp_screen.png"

    # Capture live screen if not present
    if not Path(screenshot_path).exists():
        screenshot = ImageGrab.grab()
        screenshot.save(screenshot_path)

    # Initialize history queue with initial events
    history = HistoryQueue(max_size=5)
    history.append(
        timestamp="14:25:00",
        entry="User opened VS Code to work on the parser."
    )
    history.append(
        timestamp="14:26:30",
        entry="Compiler threw segmentation fault in line 42."
    )

    current_ts = "14:30:00"
    start_time = time.time()
    result = get_sidekick_response(
        image_path=str(SCREENSHOT_PATH),
        mouse_active=False,
        current_timestamp=current_ts,
        history_queue=history,
        user_message="Why is this segfaulting?"
    )
    elapsed = time.time() - start_time

    print(f"\n[Finished in {elapsed:.2f}s]")
    print("Classification:", result.status_classification)
    print("Reaction:      ", result.reaction)
    print("Bubble Speech: ", result.bubble_speech)
    print("Activities:    ", result.detected_activities)
    print("Summary Entry: ", result.session_summary_entry)

    print("\n--- Full History Queue Contents ---")
    print(history.form_json(as_string=True))

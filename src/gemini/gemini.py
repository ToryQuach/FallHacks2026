import io
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Literal, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from PIL import Image, ImageGrab
from pydantic import BaseModel, Field

# history.py lives in src/history, so add that folder to the import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "history"))
from history import HistoryQueue  # noqa: E402

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
# Schemas
# ---------------------------------------------------------------------------
Status = Literal["FOCUSING", "STRUGGLING", "DISTRACTED", "CELEBRATING"]
Reaction = Literal["idle", "happy", "proud", "annoyed", "angry", "disappointed", "studying", "kick_screen"]


class Observation(BaseModel):
    """Step 1: what the user is doing (no personality)."""
    status_classification: Status = Field(
        description="Whether the user is on-task, stuck, distracted, or just succeeded."
    )
    detected_activities: List[str] = Field(
        description="Key apps, open tabs, or document titles visible on screen, including any social media, videos, or games."
    )
    summary: str = Field(description="1 sentence: what the user is doing right now.")


class SidekickResponse(BaseModel):
    """Step 2: how the sidekick reacts, in character."""
    reaction: Reaction = Field(
        description="The emotional or animation reaction trigger for the desktop sprite."
    )
    bubble_speech: str = Field(
        description="Short, in-character line to display in the desktop speech bubble (max 35 words)."
    )


# ---------------------------------------------------------------------------
# Prompts (persona and goals)
# ---------------------------------------------------------------------------
def load_text_or_default(filepath: Path, default: str) -> str:
    path = Path(filepath)
    if path.is_file():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return content
    return default


def load_goals(history_dir: Path = HISTORY_DIR) -> str:
    return load_text_or_default(history_dir / "goal.txt", DEFAULT_GOALS)


def load_personality(history_dir: Path = HISTORY_DIR) -> str:
    return load_text_or_default(history_dir / "personality.txt", DEFAULT_PERSONALITY)


def build_observer_instruction(goals: str) -> str:
    """Neutral prompt for get_observation(): just describe and classify."""
    return f"""You watch a user's screen and report objectively what they are doing.

## Session Goals
{goals}

## Assessment Rules
- If idle/no input while stuck on an error trace or compiler output, status is STRUGGLING.
- If non-work media or games are active, status is DISTRACTED.
- If making steady progress or tests pass, status is FOCUSING or CELEBRATING.
"""


def build_persona_instruction(personality: str, goals: str) -> str:
    """In-character prompt for get_sidekick_response()."""
    return f"""# Autonomous Desktop Side-Kick

## Persona
{personality}

Rules:
- Embody the persona directly without AI boilerplate or generic cheerleading.
- Keep `bubble_speech` under 35 words.
- React to the observation you are given, and use the recent history for continuity.

## Session Goals
{goals}
"""


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
# Shared API call with retries and model fallback
# ---------------------------------------------------------------------------
def _call_model(contents: list, schema: type[BaseModel], system_instruction: str,
                model_name: str = DEFAULT_MODEL) -> BaseModel:
    """Call Gemini and parse the reply into `schema`. Retries server errors,
    then falls back to FALLBACK_MODEL."""
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.3,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )

    models_to_try = [model_name]
    if model_name != FALLBACK_MODEL:
        models_to_try.append(FALLBACK_MODEL)

    last_err = None
    for target_model in models_to_try:
        for _attempt in range(2):
            try:
                response = get_client().models.generate_content(
                    model=target_model, contents=contents, config=config,
                )
            except errors.ServerError as e:
                last_err = e
                time.sleep(1.5)  # give a demand spike a moment to clear
                continue
            except Exception as e:
                last_err = e
                break  # not retryable on this model; try the next one

            if isinstance(getattr(response, "parsed", None), schema):
                return response.parsed
            raw_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return schema.model_validate_json(raw_text)

    raise RuntimeError(f"All model attempts failed with: {last_err}")


def _telemetry_json(current_timestamp: str, mouse_active: bool,
                    history_queue: Optional[HistoryQueue], user_message: Optional[str]) -> str:
    payload = {
        "timestamp": current_timestamp,
        "mouse_active": mouse_active,
        "rolling_history": history_queue.form_json() if history_queue else [],
        "user_direct_input": user_message or "None (Passive Monitoring)",
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# Step 1: look at the screen
# ---------------------------------------------------------------------------
def get_observation(
    image_path: str,
    mouse_active: bool,
    current_timestamp: str,
    history_queue: Optional[HistoryQueue] = None,
    goals: Optional[str] = None,
    model_name: str = DEFAULT_MODEL,
) -> Observation:
    """Send the screenshot and report what the user is doing.
    Appends the summary to `history_queue` (the only place history is added)."""
    if goals is None:
        goals = load_goals()

    image_bytes = get_optimized_image_bytes(image_path)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    prompt = (
        f"Telemetry:\n```json\n{_telemetry_json(current_timestamp, mouse_active, history_queue, None)}\n```\n"
        "Describe and classify what the user is doing in this screenshot."
    )

    observation = _call_model([prompt, image_part], Observation,
                              build_observer_instruction(goals), model_name)

    if history_queue is not None:
        history_queue.append(timestamp=current_timestamp, entry=observation.summary)
    return observation


# ---------------------------------------------------------------------------
# Step 2: react in character (text only, no image)
# ---------------------------------------------------------------------------
def get_sidekick_response(
    observation: Observation,
    current_timestamp: str,
    history_queue: Optional[HistoryQueue] = None,
    user_message: Optional[str] = None,
    personality: Optional[str] = None,
    goals: Optional[str] = None,
    model_name: str = DEFAULT_MODEL,
) -> SidekickResponse:
    """Turn an Observation into the sprite's reaction and speech bubble."""
    if personality is None:
        personality = load_personality()
    if goals is None:
        goals = load_goals()

    history = history_queue.form_json() if history_queue else []
    prompt = (
        f"Time: {current_timestamp}\n"
        f"Observation:\n```json\n{observation.model_dump_json(indent=2)}\n```\n"
        f"Recent history:\n```json\n{json.dumps(history, indent=2)}\n```\n"
        f"User says: {user_message or 'nothing (passive monitoring)'}\n"
        "React in character."
    )

    return _call_model([prompt], SidekickResponse,
                       build_persona_instruction(personality, goals), model_name)


# ---------------------------------------------------------------------------
# Quick test: python src/gemini/gemini.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    history = HistoryQueue(max_size=5)
    history.append(timestamp="14:25:00", entry="User opened VS Code to work on the parser.")
    history.append(timestamp="14:26:30", entry="Compiler threw segmentation fault in line 42.")

    start = time.time()
    obs = get_observation(str(SCREENSHOT_PATH), mouse_active=False,
                          current_timestamp="14:30:00", history_queue=history)
    reply = get_sidekick_response(obs, "14:30:00", history_queue=history,
                                  user_message="Why is this segfaulting?")
    print(f"\n[Finished in {time.time() - start:.2f}s]")
    print(obs.model_dump_json(indent=2))
    print(reply.model_dump_json(indent=2))
    print("\n--- History ---")
    print(history.form_json(as_string=True))

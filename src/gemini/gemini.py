import os
import json
from pathlib import Path
from typing import List, Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Step 1: Read GEMINI_API_KEY & Model Config from .env
# ---------------------------------------------------------------------------
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file or environment.")

# Default to Gemma 4 (falls back to gemma-4-31b-it or whatever you specify in .env)
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

client = genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Schema Definition
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
# Step 2: Build the Personality and Goal
# ---------------------------------------------------------------------------
def load_text_or_default(filepath: str, default: str) -> str:
    path = Path(filepath)
    if path.is_file():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return content
    return default

personality = load_text_or_default(
    "personality.txt",
    "You are a witty, mildly sarcastic digital desktop sidekick. Keep comments concise and sharp."
)

goals = load_text_or_default(
    "goal.txt",
    "Focus on programming, debugging, and reading documentation. Avoid social media, videos, and games."
)

system_instruction = f"""# SYSTEM INSTRUCTION: Autonomous Desktop Side-Kick Engine

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


# ---------------------------------------------------------------------------
# Step 3: Get the Response Using Current Method (Default: Gemma)
# ---------------------------------------------------------------------------
def get_sidekick_response(
    image_path: str,
    mouse_active: bool,
    current_timestamp: str,
    memory_queue: Optional[List[str]] = None,
    user_message: Optional[str] = None,
    model_name: str = DEFAULT_MODEL
) -> SidekickResponse:
    # 1. Package the screenshot
    image_bytes = Path(image_path).read_bytes()
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

    # 2. Package telemetry & context
    state_payload = {
        "timestamp": current_timestamp,
        "mouse_active": mouse_active,
        "rolling_history": memory_queue or [],
        "user_direct_input": user_message or "None (Passive Monitoring)"
    }

    prompt_text = (
        f"Telemetry:\n```json\n{json.dumps(state_payload, indent=2)}\n```\n"
        "Evaluate the screenshot against session goals and respond via the schema."
    )

    # 3. Call the API with structured output schema
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt_text, image_part],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=SidekickResponse,
            temperature=0.4,
        ),
    )

    # Direct parsed object or string fallback parsing
    if hasattr(response, "parsed") and isinstance(response.parsed, SidekickResponse):
        return response.parsed

    raw_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return SidekickResponse.model_validate_json(raw_text)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Use the saved screenshot in src/history (path is relative to this file,
    # so it works no matter which folder you run the script from)
    screenshot_path = str(Path(__file__).resolve().parent.parent / "history" / "temp_screen.png")

    result = get_sidekick_response(
        image_path=screenshot_path,
        mouse_active=False,
        current_timestamp="14:30:00",
        memory_queue=["[14:25:00] User opened VS Code to work on the parser."],
        user_message="Why is this segfaulting?"
    )

    print(f"Model used:     {DEFAULT_MODEL}")
    print("Classification:", result.status_classification)
    print("Reaction:      ", result.reaction)
    print("Bubble Speech: ", result.bubble_speech)
    print("Activities:    ", result.detected_activities)
    print("Summary Entry: ", result.session_summary_entry)
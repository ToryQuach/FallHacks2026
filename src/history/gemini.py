import os
import json
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# 1. Pydantic Structured Output Schema
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
# 2. Side-Kick Engine Class
# ---------------------------------------------------------------------------
class DesktopSidekickAgent:
    def __init__(
        self,
        personality_path: str = "personality.txt",
        goal_path: str = "goal.txt",
        api_key: Optional[str] = None
    ):
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model_name = "gemini-2.5-flash"  # Fast inference for real-time desktop loop
        
        # Load personality and session goal
        self.personality = self._read_file(personality_path, "You are a witty, mildly sarcastic digital side-kick.")
        self.goals = self._read_file(goal_path, "Complete programming tasks and avoid distractions.")
        
        # Rolling short-term memory (stores last N session_summary_entry strings)
        self.memory_queue: List[str] = []
        self.max_memory = 8

    def _read_file(self, filepath: str, fallback: str) -> str:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return content if content else fallback
        return fallback

    def build_system_instruction(self) -> str:
        return f"""# SYSTEM INSTRUCTION: Autonomous Desktop Side-Kick Engine

## 1. Persona Configuration
[INJECTED FROM personality.txt]
{self.personality}
[END PERSONALITY]

Tone Rules:
- Embody the persona authentically.
- No meta-commentary, AI assistant clichés, or robotic pleasantries.
- Keep `bubble_speech` under 35 words for compact speech bubbles.

## 2. Session Context & Goals
[INJECTED FROM goal.txt]
{self.goals}
[END SESSION_GOALS]

## 3. Evaluation Framework
- Cross-reference visible apps against goals.
- If mouse activity is False and an error trace/code is stuck on screen, classify as STRUGGLING.
- If distracting media/games are open during work, classify as DISTRACTED and select annoyed, angry, or kick_screen.
- Keep rolling summary entries tight and factual.
"""

    def analyze_frame(
        self,
        image_path: str,
        mouse_active: bool,
        current_timestamp: str,
        user_message: Optional[str] = None
    ) -> SidekickResponse:
        """
        Sends current screenshot and input state to Gemini and returns structured output.
        """
        # Upload screenshot to Files API or pass inline
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png"
        )

        # Context JSON metadata payload
        state_payload = {
            "timestamp": current_timestamp,
            "mouse_active": mouse_active,
            "rolling_history": self.memory_queue,
            "user_direct_input": user_message if user_message else "None (Passive Monitoring)"
        }

        prompt_text = (
            f"Analyze this desktop state payload:\n"
            f"```json\n{json.dumps(state_payload, indent=2)}\n```\n"
            f"Inspect the attached screenshot and output your response matching the schema."
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[prompt_text, image_part],
            config=types.GenerateContentConfig(
                system_instruction=self.build_system_instruction(),
                response_mime_type="application/json",
                response_schema=SidekickResponse,
                temperature=0.7,
            )
        )

        # Parse output into Pydantic model
        result_data: SidekickResponse = response.parsed

        # Update rolling memory queue
        self.memory_queue.append(f"[{current_timestamp}] {result_data.session_summary_entry}")
        if len(self.memory_queue) > self.max_memory:
            self.memory_queue.pop(0)

        return result_data


# ---------------------------------------------------------------------------
# 3. Example Driver Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure GEMINI_API_KEY is set in environment
    agent = DesktopSidekickAgent()

    # Simulate an evaluation cycle
    # output = agent.analyze_frame(
    #     image_path="temp_screen.png",
    #     mouse_active=True,
    #     current_timestamp="14:02:15",
    #     user_message=None
    # )
    # print("Reaction:", output.reaction)
    # print("Speech:", output.bubble_speech)
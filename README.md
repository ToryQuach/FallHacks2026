# FallHacks2026 — Digital Desktop Sidekick

A Gemini-powered desktop mascot that watches your screen, keeps you on task, and talks back in character.

The sidekick floats on top of your desktop as an animated sprite, periodically takes a screenshot, and asks Gemini to figure out whether you are focusing, struggling, distracted, or celebrating. It then reacts with a short line in a speech bubble, plays it out loud with text-to-speech, and changes its sprite animation to match its mood. You can also click it to chat directly, drag it around the screen, or poke it to force an immediate reaction.

Built for **Fall Hacks 2026**.

## Features

### AI & Observation
- **Screen-aware monitoring** — captures your screen on a configurable interval and sends a compressed screenshot to Gemini.
- **Two-stage AI pipeline** — a neutral "observer" describes and classifies what is happening, then an in-character "sidekick" decides how to react. Keeps observations objective and personality consistent.
- **Activity classification** — recognizes `FOCUSING`, `STRUGGLING`, `DISTRACTED`, and `CELEBRATING` states based on your session goal.
- **Goal-aware feedback** — you set a session goal (e.g. "Debug Dijkstra in C++"), and the sidekick judges distractions against it.
- **Rolling session memory** — a bounded history queue (30 events) gives the AI continuity across observations and conversations.
- **Direct chat** — click the mascot, type a message, and get an in-character reply that has the full observation/history context.
- **Poke / Speak button** — forces an immediate observation and reaction instead of waiting for the next timer.
- **Resilient Gemini calls** — retries server errors and automatically falls back to a secondary model if the primary fails.

### Desktop Mascot
- **Transparent, frameless, always-on-top window** — the sprite sits directly on your desktop with no window chrome.
- **Animated sprite states** — default, anger, annoyance, disappointment, excitement, happiness, and a "scroll" chat state.
- **Reaction mapping** — the AI's chosen emotion drives which animation plays.
- **Autonomous wandering** — the mascot strolls and bounces around the screen on its own.
- **Drag and drop** — pick it up and place it anywhere; it pauses roaming briefly after you drop it.
- **Inline chat input** — click to open a text box over the mascot, with word wrapping and a blinking caret. Press `Enter` to send, `Esc` to close.
- **Speech bubbles** — auto-sizing, word-wrapped bubbles that disappear after 8 seconds.
- **Responsive sprite scaling** — the mascot scales relative to your screen resolution.
- **Custom sprite support** — the mascot loads per-emotion sprite folders (`default/`, `anger/`, `happiness/`, …) and falls back to the built-in art for any missing emotion.

### Configuration & Personalities
- **Startup configuration menu** — choose a personality, session goal, session duration, sprite folder, and observation interval before launching.
- **Session timer** — optionally end the session after a set time, with a goodbye message.
- **Built-in personalities** (drop-in JSON files):
  - **Draco Malfoid** — haughty, theatrical, aristocratic mean-girl parody.
  - **Chippy on the Shoulder** — perpetually offended, grumpy cartoon mascot.
  - **5 Stages of Grief** — cycles through denial, anger, bargaining, depression, and acceptance as your code fails.
  - **Nathan the Tsundere** — huffy, defensive, and secretly caring.
- **Add your own personality** — drop a JSON file with `name`, `overview`, `tone`, `behavior`, and `boundaries` into `src/personalities/`; it appears in the menu automatically.
- **Configurable check interval** — 1–120 seconds between screen observations.

### Voice (Text-to-Speech)
- **Kokoro local TTS (default)** — free, offline, unlimited neural speech that runs on your machine.
- **Gemini TTS (optional)** — higher-quality acting voices via `TTS_ENGINE=gemini`.
- **pyttsx3 fallback** — if both neural engines fail, the system voice reads the line.
- **Per-personality voice presets** — each persona gets its own voice, accent, speed, and acting style.
- **Background speech queue** — speaking never blocks the UI, and stale lines are dropped so the voice doesn't fall behind.
- **Model warm-up** — Kokoro is preloaded in the background so the first line isn't delayed.
- **Speech cleanup** — strips markdown and emoji before speaking.

### Input Awareness & Utilities
- **Typing-aware behavior** — automatic remarks are postponed while you are typing, so the sidekick doesn't interrupt you.
- **Screenshot support** — Pillow capture on Windows/Xorg/macOS and XDG desktop-portal capture on Wayland; if capture fails, the last screenshot is reused.
- **Mouse tracking tools** — a standalone `MouseTracker` utility with a live overlay, JSONL logging, and click tracking.
- **Extras in `src/test/`** — chat-bubble 9-slice renderer, desktop-pet prototype, and prototype assets for experimentation.

## Requirements

- **Windows 10/11** (the PyQt6 overlay currently uses the Windows API; the AI/TTS pipeline itself is cross-platform)
- **Python 3.10+** (tested with Python 3.14)
- A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey)
- An internet connection for Gemini requests (Kokoro TTS itself works offline)

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/ToryQuach/FallHacks2026.git
cd FallHacks2026
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, allow it for the current user and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Or use `cmd` instead:

```bat
.venv\Scripts\activate.bat
```

### 3. Install all dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
| --- | --- |
| `google-genai` | Gemini API client (vision, chat, and TTS) |
| `pydantic` | Typed schemas for structured AI responses |
| `python-dotenv` | Loads API keys and settings from `.env` |
| `pillow` | Screenshot capture and image optimization |
| `pynput` | Cross-platform input/mouse listening |
| `pyautogui` | Mouse position tracking |
| `jeepney` | Linux/Wayland screenshot portal (installed only on Linux) |
| `PyQt6` | Transparent desktop overlay, menu, and mascot rendering |
| `pyttsx3` | Offline system-voice fallback |
| `kokoro-onnx` | Local neural text-to-speech engine |

> `kokoro-onnx` also pulls in `numpy` and `espeakng-loader` automatically.

### 4. Configure your API key

Create a `.env` file in the project root (it is git-ignored):

```env
GEMINI_API_KEY=your_api_key_here
```

Optional settings:

```env
# Override the Gemini model used for vision/chat
GEMINI_MODEL=gemini-3.5-flash-lite

# Voice engine: "kokoro" (local, default) or "gemini"
TTS_ENGINE=kokoro
```

### 5. Run the app

```powershell
python src/main.py
```

A setup window appears. Choose a personality, type a session goal, set a duration, choose how often to check your screen, then click **Launch Sidekick 🚀**.

On the first run, Kokoro downloads its model files into `src/tts/models/`; this happens once and is skipped afterward.

## Usage

| Action | Result |
| --- | --- |
| **Click the mascot** | Opens/closes the inline chat input |
| **Type + `Enter`** | Sends a message to the sidekick |
| **`Esc`** | Closes the app |
| **Drag the mascot** | Moves it anywhere on screen |
| **Click "Poke / Speak 💬"** | Forces an immediate observation and reaction |
| **Wait** | The sidekick observes, reacts, and speaks on its own timer |

## Project Structure

```text
FallHacks2026/
├── src/
│   ├── main.py               # Entry point: menu -> display + AI pipeline + TTS
│   ├── display/              # PyQt6 transparent mascot window, sprites, wandering
│   ├── gemini/               # Screenshot capture, prompts, Gemini calls, pipeline loop
│   ├── history/              # Bounded session memory + goal/personality text files
│   ├── input/                # Mouse tracking and focus timer experiments
│   ├── menu/                 # Startup configuration dialog
│   ├── personalities/        # Drop-in personality JSON files
│   ├── tts/                  # Kokoro, Gemini TTS, and offline fallbacks
│   └── test/                 # Prototypes and chat-bubble assets
├── requirements.txt
├── .env                      # Your API key (not committed)
└── README.md
```

## Troubleshooting

- **`GEMINI_API_KEY not found`** — make sure `.env` is in the project root and contains `GEMINI_API_KEY=...`.
- **No sound** — check that your speakers are connected. On Linux/macOS, an audio player (`aplay`, `paplay`, or `afplay`) must be installed; Windows uses `winsound`.
- **Kokoro download is slow** — the model is fetched once on first use. You can pre-run `python src/tts/tts.py` to trigger the download.
- **First response feels slow** — Kokoro warm-up happens in the background, and the first Gemini call includes model start-up latency.
- **Wayland screenshot permission** — GNOME asks for permission the first time; run the app from a focused terminal and click **Allow**.
- **Using your own sprites** — a custom sprite folder must contain per-emotion subfolders (`default/`, `anger/`, `happiness/`, …) with `frame_0.png`, `frame_1.png`, … inside. Missing emotions fall back to the built-in sprites.

## License

MIT — see [LICENSE](LICENSE).

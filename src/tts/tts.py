
import io
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from typing import Any, Dict, Optional, Union

from dotenv import load_dotenv

load_dotenv()

TTS_MODEL = "gemini-3.8-flash-tts"

# "kokoro": local voice, unlimited and offline (default)
# "gemini": nicer acting, but the free tier is about 10 requests a day per model
# Either way, if one fails the other is tried, then pyttsx3
TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro")

# Kokoro model files, downloaded on first use
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")

# name/style are for Gemini; kokoro/speed/lang are for Kokoro
VOICE_PRESETS: Dict[str, Dict[str, Any]] = {
    "Draco Malfoid": {
        "kokoro": "bf_emma", "speed": 0.95, "lang": "en-gb",
        "name": "Kore",
        "style": (
            "in the voice of a haughty, posh, upper-class English young woman "
            "with a crisp Received Pronunciation accent. Sound bored, superior "
            "and theatrically offended, drawing out words with disdain"
        ),
    },
    "Chippy on the Shoulder": {
        "kokoro": "am_fenrir", "speed": 1.1, "lang": "en-us",
        "name": "Fenrir",
        "style": (
            "like a grumpy, petty cartoon mascot: snappy, irritated and fed up, "
            "with exasperated sighs"
        ),
    },
    "5 Stages of Grief": {
        "kokoro": "bm_george", "speed": 0.9, "lang": "en-gb",
        "name": "Charon",
        "style": (
            "like a melodramatic stage actor in the middle of an existential "
            "crisis, with big emotional swings"
        ),
    },
    "Nathan the Tsundere": {
        "kokoro": "am_puck", "speed": 1.15, "lang": "en-us",
        "name": "Puck",
        "style": (
            "like a flustered anime tsundere boy: huffy, defensive and "
            "embarrassed, speeding up when flustered"
        ),
    },
}

DEFAULT_VOICE: Dict[str, Any] = {
    "kokoro": "af_heart", "speed": 1.0, "lang": "en-us",
    "name": "Zephyr", "style": "in a friendly, witty, slightly sarcastic voice",
}

FALLBACK_VOICE_HINTS = {
    "Draco Malfoid": ["hazel", "en-gb", "english (great britain)", "zira"],
}

Personality = Union[Dict[str, Any], str, None]

# PICKING THE VOICE


# Voice name and style for a personality dictionary, name, or None
def voice_for(personality: Personality) -> Dict[str, Any]:
    if isinstance(personality, dict):
        if isinstance(personality.get("voice"), dict):
            return {**DEFAULT_VOICE, **personality["voice"]}
        personality = personality.get("name")
    text = personality or ""
    if text in VOICE_PRESETS:
        return VOICE_PRESETS[text]
    # personality.txt holds a full description, so look for a preset name in it
    for name, preset in VOICE_PRESETS.items():
        if name.lower() in text.lower():
            return preset
    return DEFAULT_VOICE



# drop markdown and other emojis
def clean_for_speech(text: str) -> str:
    text = re.sub(r"[*_`#~]", "", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# Gemini TTS
_client = None
_model_name: Optional[str] = None

# Get client API key
def _get_client():
    global _client
    if _client is None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file or environment.")
        # TTS models and speech_config only exist on v1beta; the SDK defaults to v1
        _client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    return _client


# Get tts-model, gemini-flash-3.8-lite or whatever the first one API can see

def _tts_model() -> str:
    global _model_name
    if _model_name:
        return _model_name
    if TTS_MODEL:
        _model_name = TTS_MODEL
        return _model_name

    names = [m.name.removeprefix("models/") for m in _get_client().models.list()]
    tts_models = [n for n in names if "tts" in n]
    if not tts_models:
        raise RuntimeError("No text-to-speech model is available for this API key.")
    # Prefer the newest flash model
    tts_models.sort(key=lambda n: ("flash" in n, n), reverse=True)
    _model_name = tts_models[0]
    print(f"[tts] using {_model_name}")
    return _model_name


# Convert Gemini returned 16-bit mono PCM into a WAV header
def _pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    """Gemini returns raw 16-bit mono PCM; wrap it in a WAV header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buf.getvalue()


# Return WAV bytes of text in personality's voice
def synthesize(text: str, personality: Personality = None) -> bytes:
    from google.genai import types

    voice = voice_for(personality)
    # TTS models speak plain-text instructions aloud; this section format keeps
    # the style as direction and only the transcript gets spoken
    prompt = (
        f"### DIRECTOR'S NOTES\nStyle: Speak {voice['style']}.\n\n"
        f"### TRANSCRIPT\n{text}"
    )

    response = _get_client().models.generate_content(
        model=_tts_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice["name"])
                )
            ),
        ),
    )
    part = response.candidates[0].content.parts[0].inline_data
    # Newer models already return a full WAV file
    if (part.mime_type or "").startswith("audio/wav"):
        return part.data
    # Older ones return raw PCM, e.g. "audio/L16;codec=pcm;rate=24000"
    match = re.search(r"rate=(\d+)", part.mime_type or "")
    return _pcm_to_wav(part.data, int(match.group(1)) if match else 24000)


# Kokoro TTS (local)
_kokoro = None
_kokoro_lock = threading.Lock()


def _espeak_data_dir() -> str:
    """espeak-ng (used by Kokoro) can't open paths with non-ASCII characters
    such as デスクトップ, so copy its data to an ASCII-only folder once."""
    import espeakng_loader

    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    dst = os.path.join(base, "kokoro", "espeak-ng-data")
    if not os.path.exists(os.path.join(dst, "phontab")):
        shutil.copytree(espeakng_loader.get_data_path(), dst, dirs_exist_ok=True)
    return dst


def _get_kokoro():
    with _kokoro_lock:   # warm_up() and the speaker thread may race here
        return _load_kokoro()


def _load_kokoro():
    global _kokoro
    if _kokoro is None:
        from urllib.request import urlretrieve
        from kokoro_onnx import EspeakConfig, Kokoro

        os.makedirs(MODELS_DIR, exist_ok=True)
        for name in KOKORO_FILES:
            path = os.path.join(MODELS_DIR, name)
            if not os.path.exists(path):
                print(f"[tts] downloading {name} (first run only)...")
                urlretrieve(KOKORO_URL + name, path + ".part")
                os.replace(path + ".part", path)
        _kokoro = Kokoro(
            os.path.join(MODELS_DIR, KOKORO_FILES[0]),
            os.path.join(MODELS_DIR, KOKORO_FILES[1]),
            espeak_config=EspeakConfig(data_path=_espeak_data_dir()),
        )
    return _kokoro


def synthesize_kokoro(text: str, personality: Personality = None) -> bytes:
    """Return WAV bytes of text, spoken locally by Kokoro."""
    import numpy as np

    voice = voice_for(personality)
    samples, rate = _get_kokoro().create(
        text, voice=voice["kokoro"], speed=voice["speed"], lang=voice["lang"]
    )
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    return _pcm_to_wav(pcm, rate)



# Play the wav file
def play_wav(wav_bytes: bytes) -> None:
    """Play WAV bytes and wait until done."""
    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
        return

    # Mac / Linux: write a temp file and use the system player
    player = shutil.which("afplay") or shutil.which("aplay") or shutil.which("paplay")
    if not player:
        raise RuntimeError("No audio player found (afplay, aplay or paplay).")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        path = f.name
    try:
        subprocess.run([player, path], check=False)
    finally:
        os.remove(path)



# speak offline as fallback
def speak_offline(text: str, personality: Personality = None) -> None:
    import pyttsx3

    name = personality.get("name") if isinstance(personality, dict) else personality
    engine = pyttsx3.init()
    hints = FALLBACK_VOICE_HINTS.get(name or "", [])
    for hint in hints:
        match = next((v for v in engine.getProperty("voices")
                      if hint in f"{v.name} {v.id}".lower()), None)
        if match:
            engine.setProperty("voice", match.id)
            break
    engine.say(text)
    engine.runAndWait()
    engine.stop()

# Speak and wait until finished: TTS_ENGINE first, then the other, then pyttsx3
def speak_now(text: str, personality: Personality = None) -> None:
    text = clean_for_speech(text)
    if not text:
        return
    engines = [("kokoro", synthesize_kokoro), ("gemini", synthesize)]
    if TTS_ENGINE == "gemini":
        engines.reverse()
    for name, make_wav in engines:
        try:
            wav = make_wav(text, personality)
        except Exception as e:
            print(f"[tts] {name} failed ({str(e)[:150]})")
            continue
        play_wav(wav)
        return
    try:
        speak_offline(text, personality)
    except Exception as e:
        print(f"[tts] offline voice failed too: {e}")


_lines: "queue.Queue[tuple]" = queue.Queue(maxsize=1)
_worker: Optional[threading.Thread] = None


def _speaker_loop() -> None:
    while True:
        text, personality = _lines.get()
        speak_now(text, personality)


def warm_up() -> None:
    """Load Kokoro in the background so the first line isn't delayed."""
    if TTS_ENGINE != "kokoro":
        return

    def load():
        try:
            _get_kokoro()
        except Exception as e:
            print(f"[tts] couldn't preload Kokoro: {e}")

    threading.Thread(target=load, daemon=True).start()


def speak(text: str, personality: Personality = None) -> None:
    """Queue a line to be spoken in the background. If a line is still
    waiting, the newer one replaces it so the voice never falls behind."""
    global _worker
    if _worker is None:
        _worker = threading.Thread(target=_speaker_loop, daemon=True)
        _worker.start()
    try:
        _lines.get_nowait()   # drop a stale line that hasn't started yet
    except queue.Empty:
        pass
    _lines.put((text, personality))


if __name__ == "__main__":
    who = sys.argv[1] if len(sys.argv) > 1 else "Draco Malfoid"
    line = sys.argv[2] if len(sys.argv) > 2 else (
        "Is that really your code? How quaint. Father will hear about this."
    )
    print(f"[tts] {who}: {line}")
    speak_now(line, who)
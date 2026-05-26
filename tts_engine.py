import asyncio
import os
import tempfile
from pathlib import Path

import edge_tts

try:
    from playsound import playsound
except Exception:
    playsound = None


DEFAULT_VOICE = "en-US-AriaNeural"


async def _create_audio(text, output_path, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def _play_audio(path):
    if playsound is None:
        try:
            os.startfile(str(path))
            return True, "playsound is not installed, opened with Windows default player.", True
        except Exception as fallback_exc:
            return False, f"Audio playback failed because playsound is unavailable and fallback failed: {fallback_exc}", False

    try:
        playsound(str(path))
        return True, "", False
    except Exception as exc:
        try:
            os.startfile(str(path))
            return True, f"playsound failed, opened with Windows default player: {exc}", True
        except Exception as fallback_exc:
            return False, f"Audio playback failed: {exc}; fallback failed: {fallback_exc}", False


def speak_text(text, voice=None):
    if not text or not text.strip():
        return {"ok": False, "message": "No text was provided for TTS."}

    selected_voice = voice or os.getenv("TTS_VOICE") or DEFAULT_VOICE

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        output = Path(f.name)

    try:
        asyncio.run(_create_audio(text.strip(), output, selected_voice))
        ok, message, keep_file = _play_audio(output)
        return {"ok": ok, "message": message, "voice": selected_voice, "file": str(output)}
    except Exception as exc:
        return {"ok": False, "message": f"TTS failed: {exc}", "voice": selected_voice, "file": str(output)}
    finally:
        if "keep_file" not in locals() or not keep_file:
            try:
                output.unlink(missing_ok=True)
            except PermissionError:
                pass

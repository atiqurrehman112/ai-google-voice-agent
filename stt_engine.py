import tempfile
from pathlib import Path

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
except Exception:
    np = None
    sd = None
    sf = None


DEFAULT_SAMPLE_RATE = 16000


def list_audio_devices():
    if sd is None:
        return {
            "ok": False,
            "devices": [],
            "inputs": [],
            "outputs": [],
            "message": "sounddevice is not available. Install requirements or use manual transcript input.",
        }

    try:
        devices = sd.query_devices()
        rows = []
        for index, device in enumerate(devices):
            rows.append(
                {
                    "index": index,
                    "name": device.get("name", ""),
                    "hostapi": device.get("hostapi", ""),
                    "max_input_channels": int(device.get("max_input_channels", 0)),
                    "max_output_channels": int(device.get("max_output_channels", 0)),
                    "default_samplerate": int(float(device.get("default_samplerate", DEFAULT_SAMPLE_RATE))),
                }
            )
        return {
            "ok": True,
            "devices": rows,
            "inputs": [row for row in rows if row["max_input_channels"] > 0],
            "outputs": [row for row in rows if row["max_output_channels"] > 0],
            "message": f"Found {len(rows)} audio devices.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "devices": [],
            "inputs": [],
            "outputs": [],
            "message": f"Could not list audio devices: {exc}",
        }


def _device_index(input_device):
    if input_device in ("", None, "Default"):
        return None
    try:
        return int(input_device)
    except (TypeError, ValueError):
        return input_device


def _sample_rate_for_device(input_device):
    try:
        device = sd.query_devices(_device_index(input_device), "input")
        return int(float(device.get("default_samplerate", DEFAULT_SAMPLE_RATE)))
    except Exception:
        return DEFAULT_SAMPLE_RATE


def record_audio(seconds, input_device=None):
    if sd is None or sf is None or np is None:
        return {
            "ok": False,
            "path": "",
            "seconds": seconds,
            "sample_rate": None,
            "message": "Audio recording dependencies are unavailable. Install sounddevice, soundfile, and numpy, or use manual input.",
        }

    try:
        duration = max(1, int(seconds))
        device = _device_index(input_device)
        sample_rate = _sample_rate_for_device(device)
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=device,
        )
        sd.wait()
        audio = np.asarray(audio)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            wav_path = Path(f.name)
        sf.write(str(wav_path), audio, sample_rate)

        return {
            "ok": True,
            "path": str(wav_path),
            "seconds": duration,
            "sample_rate": sample_rate,
            "message": f"Recorded {duration} seconds.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "path": "",
            "seconds": seconds,
            "sample_rate": None,
            "message": f"Recording failed: {exc}",
        }


def transcribe_audio_file_placeholder(path=None):
    if not path:
        return {
            "ok": False,
            "text": "",
            "message": "No audio file was provided for transcription.",
            "path": path,
        }

    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.AudioFile(path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        return {
            "ok": True,
            "text": text,
            "message": "Transcription completed with SpeechRecognition.",
            "path": path,
        }
    except Exception as exc:
        return {
            "ok": False,
            "text": "",
            "message": f"Automatic STT failed. Use manual transcript input instead. Details: {exc}",
            "path": path,
        }


def transcribe_audio_file(path=None):
    return transcribe_audio_file_placeholder(path)


def listen_from_microphone(seconds=5, input_device=None):
    recording = record_audio(seconds, input_device=input_device)
    if not recording["ok"]:
        return {
            "ok": False,
            "text": "",
            "message": recording["message"],
            "path": recording.get("path", ""),
        }
    return transcribe_audio_file_placeholder(recording["path"])


def transcribe_microphone_once():
    return listen_from_microphone()

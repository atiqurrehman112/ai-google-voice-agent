import json
import time
from pathlib import Path

import pyautogui
import pyperclip


CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG = {
    "number_input": None,
    "call_button": None,
    "end_call_button": None,
    "keypad_clear": None,
    "pyautogui_pause": 0.2,
    "selected_input_device": None,
    "selected_output_device": None,
    "recording_seconds": 5,
    "tts_voice": "en-US-AriaNeural",
}

FAILSAFE_MESSAGE = "PyAutoGUI failsafe is on: move the mouse to the top-left corner to stop automation."

pyautogui.FAILSAFE = True


def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    return merged


def save_config(config):
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def save_coordinate(key, position):
    config = load_config()
    config[key] = {"x": int(position[0]), "y": int(position[1])}
    save_config(config)


def capture_position():
    pos = pyautogui.position()
    return int(pos.x), int(pos.y)


def _get_coordinate(key):
    config = load_config()
    coord = config.get(key)
    if not coord:
        raise ValueError(f"Missing coordinate '{key}'. Capture it in Setup Coordinates first.")
    return int(coord["x"]), int(coord["y"])


def get_failsafe_message():
    return FAILSAFE_MESSAGE


def safe_pause(seconds):
    time.sleep(max(0, float(seconds)))


def _pause():
    safe_pause(load_config()["pyautogui_pause"])


def click_number_input():
    x, y = _get_coordinate("number_input")
    pyautogui.click(x, y)
    _pause()


def type_phone_number(phone):
    pyperclip.copy(str(phone))
    pyautogui.hotkey("ctrl", "a")
    _pause()
    pyautogui.press("backspace")
    _pause()
    pyautogui.hotkey("ctrl", "v")
    _pause()


def click_call():
    x, y = _get_coordinate("call_button")
    pyautogui.click(x, y)
    _pause()


def click_end():
    x, y = _get_coordinate("end_call_button")
    pyautogui.click(x, y)
    _pause()


def click_keypad_clear():
    x, y = _get_coordinate("keypad_clear")
    pyautogui.click(x, y)
    _pause()


def call_number(phone):
    click_number_input()
    type_phone_number(phone)
    click_call()

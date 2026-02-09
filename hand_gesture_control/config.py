import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

DEFAULT_GESTURE_TO_ACTION: Dict[str, Any] = {
    "OPEN_PALM": "SPACE",
    "FOUR_FINGERS": None,
    "INDEX_UP": "RIGHT",
    "TWO_FINGERS": "LEFT",
    "THREE_FINGERS": None,
    "FIST": "M",
    "ROCK": None,
    "OK_SIGN": None,
    "PINCH": None,
    "THUMB_UP": "VOLUME_UP",
    "THUMB_DOWN": "VOLUME_DOWN",
    "BOTH_OPEN_PALM": None,
    "BOTH_FIST": None,
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "camera_index": 0,
    "min_detection_confidence": 0.6,
    "min_tracking_confidence": 0.6,
    "max_num_hands": 2,
    "gesture_window_size": 8,
    "gesture_min_votes": 6,
    "gesture_min_stable_time": 0.2,
    "gesture_min_frames": 4,
    "gesture_switch_multiplier": 1.4,
    "gesture_unknown_timeout": 0.5,
    "thumb_extended_ratio": 0.35,
    "pinch_ratio": 0.22,
    "thumb_up_down_threshold": 0.05,
    "cooldown_seconds": 0.6,
    "mirror": True,
    "backend": "auto",
    "task_model_path": "models/hand_landmarker.task",
    "camera_width": None,
    "camera_height": None,
    "headless": False,
    "start_paused": False,
    "fullscreen": False,
    "windowed_fullscreen": False,
    "windowed_margin": 60,
    "display_width": None,
    "display_height": None,
    "overlay_scale": "auto",
    "overlay_alpha": 0.55,
    "overlay_padding": 14,
    "overlay_line_gap": 10,
    "landmark_scale": "auto",
    "controls_enabled": True,
    "controls_position": "right",
    "controls_scale": 1.0,
    "controls_alpha": 0.6,
    "controls_margin": 16,
    "controls_gap": 10,
    "log_enabled": False,
    "log_mode": "actions",
    "log_path": "logs/gesture_events.log",
    "gesture_to_action": DEFAULT_GESTURE_TO_ACTION,
    "active_profile": "default",
    "profiles": {
        "default": {
            "gesture_to_action": DEFAULT_GESTURE_TO_ACTION,
        }
    },
}


def _merge_dict(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: str) -> Dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    config_path = Path(path)
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in config file: {config_path}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Config file must contain a JSON object: {config_path}")
        config = _merge_dict(config, data)
    return config


def save_config(path: str, config: Dict[str, Any]) -> None:
    config_path = Path(path)
    config_path.write_text(
        json.dumps(config, indent=2, sort_keys=False, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

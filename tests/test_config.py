import json

import pytest

from hand_gesture_control.config import DEFAULT_CONFIG, load_config, save_config


def test_missing_file_returns_defaults(tmp_path):
    config = load_config(str(tmp_path / "missing.json"))
    assert config == DEFAULT_CONFIG


def test_overrides_are_merged_into_nested_dicts(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"cooldown_seconds": 1.5, "gesture_to_action": {"FIST": "ENTER"}}),
        encoding="utf-8",
    )
    config = load_config(str(path))
    assert config["cooldown_seconds"] == 1.5
    assert config["gesture_to_action"]["FIST"] == "ENTER"
    # Keys that were not overridden keep their defaults.
    assert config["gesture_to_action"]["OPEN_PALM"] == "SPACE"


def test_loading_does_not_mutate_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"gesture_to_action": {"FIST": "ENTER"}}), encoding="utf-8")
    load_config(str(path))
    assert DEFAULT_CONFIG["gesture_to_action"]["FIST"] == "M"


def test_invalid_json_raises_value_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_config(str(path))


def test_non_object_raises_value_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_config(str(path))


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "config.json"
    config = load_config(str(path))
    config["camera_index"] = 2
    save_config(str(path), config)
    assert load_config(str(path))["camera_index"] == 2


def test_shipped_config_loads():
    config = load_config("config.json")
    assert config["active_profile"] in config["profiles"]

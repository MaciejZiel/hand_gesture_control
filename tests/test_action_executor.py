import sys
import types

import pytest


class _Key:
    """Stand-in for pynput.keyboard.Key members."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Key.{self.name}"


class _KeyEnum:
    def __getattr__(self, name):
        return _Key(name)


class _FakeController:
    def __init__(self):
        self.events = []

    def press(self, key):
        self.events.append(("press", key))

    def release(self, key):
        self.events.append(("release", key))

    def type(self, text):
        self.events.append(("type", text))


@pytest.fixture
def executor_cls(monkeypatch):
    # pynput needs a display server at import time; the tests only exercise parsing
    # and call ordering, so a stub keeps them runnable on a headless CI runner.
    keyboard = types.ModuleType("pynput.keyboard")
    keyboard.Controller = _FakeController
    keyboard.Key = _KeyEnum()
    pynput = types.ModuleType("pynput")
    pynput.keyboard = keyboard
    monkeypatch.setitem(sys.modules, "pynput", pynput)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)
    monkeypatch.delitem(sys.modules, "hand_gesture_control.action_executor", raising=False)
    from hand_gesture_control.action_executor import ActionExecutor

    return ActionExecutor


def test_macro_string_is_split_on_semicolons_and_commas(executor_cls):
    executor = executor_cls(dry_run=True)
    assert executor._normalize_steps("CTRL+L;TEXT:hi, ENTER") == ["CTRL+L", "TEXT:hi", "ENTER"]


def test_empty_actions_do_nothing(executor_cls):
    executor = executor_cls(dry_run=True)
    assert executor.trigger("") is False
    assert executor.trigger(None) is False
    assert executor.trigger([]) is False


def test_unknown_key_is_rejected(executor_cls):
    executor = executor_cls(dry_run=True)
    assert executor.trigger("NOT_A_KEY") is False


def test_invalid_delay_is_rejected(executor_cls):
    executor = executor_cls(dry_run=True)
    assert executor.trigger("DELAY:abc") is False


def test_dry_run_does_not_touch_the_keyboard(executor_cls, capsys):
    executor = executor_cls(dry_run=True)
    assert executor.trigger("CTRL+SHIFT+P;TEXT:hello") is True
    assert executor._controller.events == []
    out = capsys.readouterr().out
    assert "[DRY-RUN] CTRL+SHIFT+P" in out
    assert "[DRY-RUN] TEXT:hello" in out


def test_shortcut_presses_in_order_and_releases_in_reverse(executor_cls):
    executor = executor_cls()
    assert executor.trigger("ctrl+c") is True
    events = executor._controller.events
    assert [kind for kind, _ in events] == ["press", "press", "release", "release"]
    assert events[0][1].name == "ctrl"
    assert events[1][1] == "c"
    assert events[2][1] == "c"
    assert events[3][1].name == "ctrl"


def test_function_keys_and_text(executor_cls):
    executor = executor_cls()
    assert executor.trigger(["F5", "TEXT:Hello World"]) is True
    events = executor._controller.events
    assert events[0][1].name == "f5"
    assert events[-1] == ("type", "Hello World")


def test_function_key_out_of_range_is_unknown(executor_cls):
    executor = executor_cls(dry_run=True)
    assert executor.trigger("F13") is False

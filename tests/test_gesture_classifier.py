from dataclasses import dataclass

from hand_gesture_control.gesture_classifier import (
    FIST,
    FOUR_FINGERS,
    INDEX_UP,
    OK_SIGN,
    OPEN_PALM,
    PINCH,
    ROCK,
    THREE_FINGERS,
    THUMB_DOWN,
    THUMB_UP,
    TWO_FINGERS,
    GestureClassifier,
)


@dataclass
class Landmark:
    x: float
    y: float


def _make_landmarks(
    thumb_extended: bool = True,
    index_extended: bool = True,
    middle_extended: bool = True,
    ring_extended: bool = True,
    pinky_extended: bool = True,
    pinch: bool = False,
    thumb_up: bool = False,
    thumb_down: bool = False,
):
    lms = [Landmark(0.5, 0.9) for _ in range(21)]

    # Palm reference
    lms[0] = Landmark(0.5, 0.9)
    lms[9] = Landmark(0.5, 0.6)

    def set_finger(mcp, pip, tip, x, extended):
        if extended:
            lms[mcp] = Landmark(x, 0.6)
            lms[pip] = Landmark(x, 0.45)
            lms[tip] = Landmark(x, 0.3)
        else:
            lms[mcp] = Landmark(x, 0.6)
            lms[pip] = Landmark(x, 0.75)
            lms[tip] = Landmark(x, 0.85)

    set_finger(5, 6, 8, 0.4, index_extended)
    set_finger(9, 10, 12, 0.5, middle_extended)
    set_finger(13, 14, 16, 0.6, ring_extended)
    set_finger(17, 18, 20, 0.7, pinky_extended)

    # Thumb reference point (5) already set by index MCP
    if thumb_extended:
        lms[4] = Landmark(0.2, 0.6)
    else:
        lms[4] = Landmark(0.37, 0.6)

    if pinch:
        lms[4] = Landmark(0.42, 0.32)
        lms[8] = Landmark(0.4, 0.3)

    if thumb_up:
        lms[4] = Landmark(0.2, 0.7)
    if thumb_down:
        lms[4] = Landmark(0.2, 0.97)

    return lms


class _Hand:
    def __init__(self, landmarks):
        self.landmark = landmarks


def _classify(**kwargs):
    classifier = GestureClassifier()
    return classifier.classify(_Hand(_make_landmarks(**kwargs)))


def test_open_palm():
    assert _classify() == OPEN_PALM


def test_four_fingers():
    assert _classify(thumb_extended=False) == FOUR_FINGERS


def test_fist():
    assert (
        _classify(
            thumb_extended=False,
            index_extended=False,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
        )
        == FIST
    )


def test_index_up():
    assert (
        _classify(
            thumb_extended=False,
            index_extended=True,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
        )
        == INDEX_UP
    )


def test_two_fingers():
    assert (
        _classify(
            thumb_extended=False,
            index_extended=True,
            middle_extended=True,
            ring_extended=False,
            pinky_extended=False,
        )
        == TWO_FINGERS
    )


def test_three_fingers():
    assert (
        _classify(
            thumb_extended=False,
            index_extended=True,
            middle_extended=True,
            ring_extended=True,
            pinky_extended=False,
        )
        == THREE_FINGERS
    )


def test_rock():
    assert (
        _classify(
            thumb_extended=False,
            index_extended=True,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=True,
        )
        == ROCK
    )


def test_ok_sign():
    assert (
        _classify(
            thumb_extended=True,
            index_extended=True,
            middle_extended=True,
            ring_extended=True,
            pinky_extended=True,
            pinch=True,
        )
        == OK_SIGN
    )


def test_pinch():
    assert (
        _classify(
            thumb_extended=True,
            index_extended=True,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
            pinch=True,
        )
        == PINCH
    )


def test_thumb_up_down():
    assert (
        _classify(
            thumb_extended=True,
            index_extended=False,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
            thumb_up=True,
        )
        == THUMB_UP
    )
    assert (
        _classify(
            thumb_extended=True,
            index_extended=False,
            middle_extended=False,
            ring_extended=False,
            pinky_extended=False,
            thumb_down=True,
        )
        == THUMB_DOWN
    )

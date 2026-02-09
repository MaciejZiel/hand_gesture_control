import math
from typing import Optional

GESTURE_UNKNOWN = "UNKNOWN"
OPEN_PALM = "OPEN_PALM"
FOUR_FINGERS = "FOUR_FINGERS"
FIST = "FIST"
INDEX_UP = "INDEX_UP"
TWO_FINGERS = "TWO_FINGERS"
THREE_FINGERS = "THREE_FINGERS"
ROCK = "ROCK"
OK_SIGN = "OK_SIGN"
PINCH = "PINCH"
THUMB_UP = "THUMB_UP"
THUMB_DOWN = "THUMB_DOWN"
THUMB = "THUMB"


class GestureClassifier:
    def __init__(
        self,
        thumb_up_down_threshold: float = 0.05,
        thumb_extended_ratio: float = 0.35,
        pinch_ratio: float = 0.22,
    ) -> None:
        self.thumb_up_down_threshold = thumb_up_down_threshold
        self.thumb_extended_ratio = thumb_extended_ratio
        self.pinch_ratio = pinch_ratio

    def classify(self, hand_landmarks) -> str:
        if hand_landmarks is None:
            return GESTURE_UNKNOWN

        lms = hand_landmarks.landmark
        if len(lms) < 21:
            return GESTURE_UNKNOWN

        def dist(idx_a: int, idx_b: int) -> float:
            dx = lms[idx_a].x - lms[idx_b].x
            dy = lms[idx_a].y - lms[idx_b].y
            return math.hypot(dx, dy)

        palm_size = dist(0, 9)
        if palm_size == 0:
            return GESTURE_UNKNOWN

        thumb_extended = dist(4, 5) > palm_size * self.thumb_extended_ratio
        index_extended = self._is_extended(lms, tip=8, pip=6, mcp=5)
        middle_extended = self._is_extended(lms, tip=12, pip=10, mcp=9)
        ring_extended = self._is_extended(lms, tip=16, pip=14, mcp=13)
        pinky_extended = self._is_extended(lms, tip=20, pip=18, mcp=17)

        thumb_index_dist = dist(4, 8)
        pinch = thumb_index_dist < palm_size * self.pinch_ratio

        if pinch and middle_extended and ring_extended and pinky_extended:
            return OK_SIGN

        if pinch and not middle_extended and not ring_extended and not pinky_extended:
            return PINCH

        if index_extended and middle_extended and ring_extended and pinky_extended:
            return OPEN_PALM if thumb_extended else FOUR_FINGERS

        if (
            not index_extended
            and not middle_extended
            and not ring_extended
            and not pinky_extended
            and not thumb_extended
        ):
            return FIST

        if index_extended and pinky_extended and not middle_extended and not ring_extended:
            return ROCK

        if index_extended and middle_extended and ring_extended and not pinky_extended:
            return THREE_FINGERS

        if index_extended and not middle_extended and not ring_extended and not pinky_extended:
            return INDEX_UP

        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return TWO_FINGERS

        if (
            thumb_extended
            and not index_extended
            and not middle_extended
            and not ring_extended
            and not pinky_extended
        ):
            thumb_tip_y = lms[4].y
            wrist_y = lms[0].y
            if thumb_tip_y < wrist_y - self.thumb_up_down_threshold:
                return THUMB_UP
            if thumb_tip_y > wrist_y + self.thumb_up_down_threshold:
                return THUMB_DOWN
            return THUMB

        return GESTURE_UNKNOWN

    @staticmethod
    def _is_extended(landmarks, tip: int, pip: int, mcp: int) -> bool:
        return landmarks[tip].y < landmarks[pip].y < landmarks[mcp].y

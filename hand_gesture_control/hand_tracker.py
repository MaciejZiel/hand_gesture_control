from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp

HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
]


class HandTracker:
    def __init__(
        self,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
        backend: str = "auto",
        model_path: Optional[str] = None,
        landmark_scale: float = 1.0,
    ) -> None:
        self._backend = None
        self._hands = None
        self._tasks_landmarker = None
        self._drawing_utils = None
        self._drawing_styles = None
        self._mp_hands = None
        self._mp_image_cls = None
        self._mp_image_format = None
        self._landmark_scale = landmark_scale

        backend = backend.lower()
        if backend not in {"auto", "solutions", "tasks"}:
            raise ValueError(f"Unsupported backend: {backend}")

        has_solutions = hasattr(mp, "solutions")
        if backend in {"auto", "solutions"} and has_solutions:
            self._backend = "solutions"
            self._mp_hands = mp.solutions.hands
            self._drawing_utils = mp.solutions.drawing_utils
            self._drawing_styles = mp.solutions.drawing_styles
            self._hands = self._mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_num_hands,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            return

        if backend == "solutions" and not has_solutions:
            raise ValueError(
                "MediaPipe 'solutions' API is not available in this installation. "
                "Use backend=tasks with a hand_landmarker.task model, or install "
                "MediaPipe on Python 3.11/3.10 where solutions are included."
            )

        self._backend = "tasks"
        if not model_path:
            raise ValueError(
                "MediaPipe tasks backend requires a hand_landmarker.task model file. "
                "Set task_model_path in config.json or pass --model."
            )
        model_file = Path(model_path)
        if not model_file.is_file():
            raise ValueError(f"Hand landmarker model file not found: {model_file}")

        try:
            from mediapipe.tasks.python import core, vision
            from mediapipe.tasks.python.vision.core.image import Image, ImageFormat
        except Exception as exc:  # pragma: no cover - defensive for broken installs
            raise ValueError("MediaPipe tasks API is not available in this installation.") from exc

        options = vision.HandLandmarkerOptions(
            base_options=core.base_options.BaseOptions(model_asset_path=str(model_file)),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._tasks_landmarker = vision.HandLandmarker.create_from_options(options)
        self._mp_image_cls = Image
        self._mp_image_format = ImageFormat

    def process(self, frame_bgr) -> Tuple[List[object], object]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        if self._backend == "solutions":
            results = self._hands.process(rgb)
            return list(results.multi_hand_landmarks or []), results

        mp_image = self._mp_image_cls(image_format=self._mp_image_format.SRGB, data=rgb)
        results = self._tasks_landmarker.detect(mp_image)
        if results.hand_landmarks:
            return [SimpleNamespace(landmark=lms) for lms in results.hand_landmarks], results
        return [], results

    def draw_landmarks(self, frame_bgr, hand_landmarks) -> None:
        if hand_landmarks is None:
            return
        if not isinstance(hand_landmarks, list):
            hand_landmarks = [hand_landmarks]
        if not hand_landmarks:
            return

        height, width = frame_bgr.shape[:2]
        base_scale = height / 720.0
        scale = max(0.5, self._landmark_scale) * base_scale
        radius = max(2, int(round(3 * scale)))
        thickness = max(1, int(round(2 * scale)))

        for hand in hand_landmarks:
            for start, end in HAND_CONNECTIONS:
                start_lm = hand.landmark[start]
                end_lm = hand.landmark[end]
                start_pt = (int(start_lm.x * width), int(start_lm.y * height))
                end_pt = (int(end_lm.x * width), int(end_lm.y * height))
                cv2.line(frame_bgr, start_pt, end_pt, (0, 255, 0), thickness)

            for lm in hand.landmark:
                pt = (int(lm.x * width), int(lm.y * height))
                cv2.circle(frame_bgr, pt, radius, (0, 255, 0), -1)

    def close(self) -> None:
        if self._backend == "solutions" and self._hands is not None:
            self._hands.close()
        if self._backend == "tasks" and self._tasks_landmarker is not None:
            self._tasks_landmarker.close()

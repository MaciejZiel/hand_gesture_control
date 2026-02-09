import argparse
import statistics
import time
from pathlib import Path

import cv2

from .action_executor import ActionExecutor
from .config import load_config, save_config
from .gesture_classifier import GESTURE_UNKNOWN, GestureClassifier
from .gesture_smoother import GestureSmoother
from .hand_tracker import HandTracker

WINDOW_TITLE = "Hand Gesture Control"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hand gesture control MVP")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not send key presses, only log actions",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="Camera index (overrides config)",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "solutions", "tasks"],
        default=None,
        help="Backend to use: auto, solutions, tasks",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Path to hand_landmarker.task model (for tasks backend)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Active profile name (overrides config)",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles and exit",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run calibration wizard and save thresholds",
    )
    parser.add_argument(
        "--calibration-samples",
        type=int,
        default=30,
        help="Samples per calibration step (default: 30)",
    )
    parser.add_argument(
        "--mirror",
        dest="mirror",
        action="store_true",
        help="Mirror the camera preview",
    )
    parser.add_argument(
        "--no-mirror",
        dest="mirror",
        action="store_false",
        help="Do not mirror the camera preview",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Run without UI window",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run with UI window",
    )
    parser.add_argument(
        "--paused",
        dest="paused",
        action="store_true",
        help="Start with actions paused",
    )
    parser.add_argument(
        "--no-paused",
        dest="paused",
        action="store_false",
        help="Start with actions enabled",
    )
    parser.add_argument(
        "--fullscreen",
        dest="fullscreen",
        action="store_true",
        help="Run in fullscreen mode",
    )
    parser.add_argument(
        "--no-fullscreen",
        dest="fullscreen",
        action="store_false",
        help="Run in windowed mode",
    )
    parser.set_defaults(mirror=None, fullscreen=None, headless=None, paused=None)
    return parser.parse_args()


def _resolve_config_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_file():
        return path
    local_path = Path.cwd() / path_str
    if local_path.is_file():
        return local_path
    return path


def _resolve_model_path(path_str: str, config_path: Path) -> Path:
    path = Path(path_str)
    if path.is_file():
        return path
    if config_path and config_path.is_file():
        candidate = config_path.parent / path_str
        if candidate.is_file():
            return candidate
    candidate = Path.cwd() / path_str
    if candidate.is_file():
        return candidate
    return path


def _resolve_log_path(path_str: str, config_path: Path) -> Path:
    path = Path(path_str)
    if path.is_file():
        return path
    if config_path and config_path.is_file():
        candidate = config_path.parent / path_str
        return candidate
    return Path.cwd() / path_str


def _normalize_profiles(config: dict) -> tuple[dict, list[str], str]:
    default_map = config.get("gesture_to_action") or {}
    profiles_raw = config.get("profiles") or {}
    profiles: dict = {}

    if isinstance(profiles_raw, dict):
        for name, value in profiles_raw.items():
            if isinstance(value, dict) and "gesture_to_action" in value:
                mapping = value.get("gesture_to_action") or {}
            elif isinstance(value, dict):
                mapping = value
            else:
                continue
            profiles[str(name)] = {"gesture_to_action": mapping}

    if "default" not in profiles:
        profiles["default"] = {"gesture_to_action": default_map}
    else:
        if default_map:
            merged = dict(default_map)
            merged.update(profiles["default"].get("gesture_to_action") or {})
            profiles["default"]["gesture_to_action"] = merged

    if not profiles:
        profiles = {"default": {"gesture_to_action": default_map}}

    profile_names = list(profiles.keys())
    active_profile = config.get("active_profile", "default")
    if active_profile not in profiles:
        active_profile = profile_names[0]

    return profiles, profile_names, active_profile


def _resolve_action(gesture: str, profiles: dict, active_profile: str) -> str | None:
    if not gesture:
        return None
    active_map = profiles.get(active_profile, {}).get("gesture_to_action", {}) or {}
    if gesture in active_map:
        return active_map.get(gesture)
    fallback_map = profiles.get("default", {}).get("gesture_to_action", {}) or {}
    if gesture in fallback_map:
        return fallback_map.get(gesture)

    if gesture.startswith(("LEFT_", "RIGHT_", "BOTH_")):
        base = gesture.split("_", 1)[1]
        if base in active_map:
            return active_map.get(base)
        return fallback_map.get(base)

    return None


def _get_screen_size() -> tuple[int, int] | tuple[None, None]:
    try:
        import tkinter as tk
    except Exception:
        return None, None

    root = tk.Tk()
    root.withdraw()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()
    return width, height


def _auto_overlay_scale(frame_height: int, base_height: int = 720, base_scale: float = 0.7) -> float:
    scale = (frame_height / base_height) * base_scale
    return max(0.6, min(1.4, scale))


def _compute_controls(
    frame_shape,
    labels,
    font_scale: float,
    thickness: int,
    position: str,
    scale: float,
    margin: int,
    gap: int,
):
    font = cv2.FONT_HERSHEY_SIMPLEX
    control_font_scale = max(0.5, font_scale * scale)
    sizes = [cv2.getTextSize(label, font, control_font_scale, thickness) for label in labels]
    max_w = max(size[0][0] for size in sizes)
    max_h = max(size[0][1] for size in sizes)
    pad = max(6, int(round(8 * control_font_scale)))
    btn_w = max_w + pad * 2
    btn_h = max_h + pad * 2

    height, width = frame_shape[:2]
    rects = []

    pos = position.lower()
    if pos in {"top", "top-right", "top-left"}:
        total_w = len(labels) * btn_w + max(0, len(labels) - 1) * gap
        y = margin
        if pos == "top-left":
            x_start = margin
        else:
            x_start = width - margin - total_w
        for i, label in enumerate(labels):
            x1 = x_start + i * (btn_w + gap)
            y1 = y
            rects.append((label, (x1, y1, x1 + btn_w, y1 + btn_h), control_font_scale, pad))
        return rects

    total_h = len(labels) * btn_h + max(0, len(labels) - 1) * gap
    x = width - margin - btn_w
    y_start = (height - total_h) // 2
    for i, label in enumerate(labels):
        y1 = y_start + i * (btn_h + gap)
        rects.append((label, (x, y1, x + btn_w, y1 + btn_h), control_font_scale, pad))
    return rects


def _draw_controls(frame, controls, alpha: float, thickness: int) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    for label, (x1, y1, x2, y2), font_scale, pad in controls:
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), max(1, thickness))
        text_size, _ = cv2.getTextSize(label, font, font_scale, thickness)
        text_x = x1 + pad
        text_y = y1 + pad + text_size[1]
        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )


def _draw_overlay_panel(
    frame,
    items,
    font_scale: float,
    thickness: int,
    alpha: float,
    padding: int,
    line_gap: int,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    sizes = [cv2.getTextSize(text, font, font_scale, thickness) for text, _ in items]
    max_width = max(size[0][0] for size in sizes) if sizes else 0
    max_height = max(size[0][1] for size in sizes) if sizes else 0
    baseline = max(size[1] for size in sizes) if sizes else 0

    panel_width = max_width + padding * 2
    line_height = max_height + baseline
    panel_height = padding * 2 + len(items) * line_height + max(0, len(items) - 1) * line_gap

    x, y = 12, 12
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + panel_width, y + panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    cursor_y = y + padding + max_height
    for (text, color) in items:
        cv2.putText(
            frame,
            text,
            (x + padding, cursor_y),
            font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )
        cursor_y += line_height + line_gap


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _run_calibration(
    camera_index: int,
    backend: str,
    model_path: str | None,
    min_detection_confidence: float,
    min_tracking_confidence: float,
    mirror: bool,
    display_width: int | None,
    display_height: int | None,
    overlay_scale: float | str,
    overlay_alpha: float,
    overlay_padding: int,
    overlay_line_gap: int,
    landmark_scale: float,
    samples_per_step: int,
) -> dict | None:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Unable to open camera index {camera_index}")
        return None

    try:
        tracker = HandTracker(
            max_num_hands=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            backend=backend,
            model_path=model_path,
            landmark_scale=landmark_scale,
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        cap.release()
        return None

    def _dist(lms, a: int, b: int) -> float:
        dx = lms[a].x - lms[b].x
        dy = lms[a].y - lms[b].y
        return (dx * dx + dy * dy) ** 0.5

    steps = [
        ("OPEN PALM (thumb out)", lambda lms, palm: _dist(lms, 4, 5) / palm),
        ("PINCH (thumb + index)", lambda lms, palm: _dist(lms, 4, 8) / palm),
    ]

    results: dict[str, float] = {}
    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
    if display_width and display_height:
        cv2.resizeWindow(WINDOW_TITLE, int(display_width), int(display_height))

    try:
        for step_index, (label, ratio_fn) in enumerate(steps, start=1):
            samples: list[float] = []
            while len(samples) < samples_per_step:
                ok, frame = cap.read()
                if not ok:
                    print("[WARN] Camera frame not received")
                    return None

                if mirror:
                    frame = cv2.flip(frame, 1)

                hand_landmarks_list, _ = tracker.process(frame)
                display_frame = frame
                if display_width and display_height:
                    display_frame = cv2.resize(
                        frame,
                        (int(display_width), int(display_height)),
                        interpolation=cv2.INTER_LINEAR
                        if display_width >= frame.shape[1]
                        else cv2.INTER_AREA,
                    )
                if hand_landmarks_list:
                    tracker.draw_landmarks(display_frame, hand_landmarks_list)

                if hand_landmarks_list:
                    lms = hand_landmarks_list[0].landmark
                    palm = _dist(lms, 0, 9)
                    if palm > 0:
                        ratio = ratio_fn(lms, palm)
                        if ratio > 0:
                            samples.append(ratio)

                if isinstance(overlay_scale, str) and overlay_scale.lower() == "auto":
                    font_scale = _auto_overlay_scale(display_frame.shape[0])
                else:
                    try:
                        font_scale = float(overlay_scale)
                    except (TypeError, ValueError):
                        font_scale = 0.7

                thickness = max(1, int(round(font_scale * 2)))
                colors = {
                    "title": (255, 200, 0),
                    "text": (245, 245, 245),
                    "muted": (180, 180, 180),
                }
                overlay_items = [
                    ("CALIBRATION", colors["title"]),
                    (f"Step {step_index}/2: {label}", colors["text"]),
                    (f"Samples: {len(samples)}/{samples_per_step}", colors["text"]),
                    ("Hold steady. Press Q or Esc to cancel.", colors["muted"]),
                ]

                _draw_overlay_panel(
                    display_frame,
                    overlay_items,
                    font_scale=font_scale,
                    thickness=thickness,
                    alpha=overlay_alpha,
                    padding=overlay_padding,
                    line_gap=overlay_line_gap,
                )

                cv2.imshow(WINDOW_TITLE, display_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    return None

            median_value = statistics.median(samples)
            results[label] = float(median_value)
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        if log_file:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"{timestamp} [INFO] Session ended\n")
            log_file.close()

    thumb_ratio = results.get("OPEN PALM (thumb out)")
    pinch_ratio = results.get("PINCH (thumb + index)")
    if thumb_ratio is None or pinch_ratio is None:
        return None

    calibrated = {
        "thumb_extended_ratio": _clamp(thumb_ratio * 0.7, 0.2, 0.6),
        "pinch_ratio": _clamp(pinch_ratio * 1.2, 0.1, 0.4),
    }
    return calibrated


def main() -> int:
    args = parse_args()
    config_path = _resolve_config_path(args.config)
    config = load_config(str(config_path))

    profiles, profile_names, active_profile = _normalize_profiles(config)
    if args.profile:
        if args.profile not in profiles:
            available = ", ".join(profile_names)
            print(f"[ERROR] Unknown profile '{args.profile}'. Available: {available}")
            return 1
        active_profile = args.profile
    if args.list_profiles:
        print("Available profiles:")
        for name in profile_names:
            print(f" - {name}")
        return 0

    camera_index = args.camera if args.camera is not None else config.get("camera_index", 0)
    min_detection_confidence = config.get("min_detection_confidence", 0.6)
    min_tracking_confidence = config.get("min_tracking_confidence", 0.6)
    max_num_hands = int(config.get("max_num_hands", 2))
    max_num_hands = max(1, min(2, max_num_hands))
    window_size = config.get("gesture_window_size", 8)
    min_votes = config.get("gesture_min_votes", 6)
    min_stable_time = float(config.get("gesture_min_stable_time", 0.2))
    min_frames = int(config.get("gesture_min_frames", 4))
    switch_multiplier = float(config.get("gesture_switch_multiplier", 1.4))
    unknown_timeout = float(config.get("gesture_unknown_timeout", 0.5))
    thumb_extended_ratio = float(config.get("thumb_extended_ratio", 0.35))
    pinch_ratio = float(config.get("pinch_ratio", 0.22))
    thumb_up_down_threshold = float(config.get("thumb_up_down_threshold", 0.05))
    cooldown_seconds = config.get("cooldown_seconds", 0.6)
    mirror = config.get("mirror", True)
    camera_width = config.get("camera_width")
    camera_height = config.get("camera_height")
    headless = bool(config.get("headless", False))
    start_paused = bool(config.get("start_paused", False))
    overlay_scale = config.get("overlay_scale", "auto")
    overlay_alpha = float(config.get("overlay_alpha", 0.55))
    overlay_padding = int(config.get("overlay_padding", 14))
    overlay_line_gap = int(config.get("overlay_line_gap", 10))
    fullscreen = config.get("fullscreen", False)
    windowed_fullscreen = config.get("windowed_fullscreen", False)
    windowed_margin = int(config.get("windowed_margin", 60))
    display_width = config.get("display_width")
    display_height = config.get("display_height")
    landmark_scale = config.get("landmark_scale", "auto")
    controls_enabled = bool(config.get("controls_enabled", True))
    controls_position = str(config.get("controls_position", "right"))
    controls_scale = float(config.get("controls_scale", 1.0))
    controls_alpha = float(config.get("controls_alpha", 0.6))
    controls_margin = int(config.get("controls_margin", 16))
    controls_gap = int(config.get("controls_gap", 10))
    log_enabled = bool(config.get("log_enabled", False))
    log_mode = str(config.get("log_mode", "actions")).lower()
    log_path = str(config.get("log_path", "logs/gesture_events.log"))
    if args.mirror is not None:
        mirror = args.mirror
    if args.headless is not None:
        headless = args.headless
    if args.paused is not None:
        start_paused = args.paused
    if args.fullscreen is not None:
        fullscreen = args.fullscreen

    backend = args.backend or config.get("backend", "auto")
    model_path = args.model or config.get("task_model_path")
    if model_path:
        model_path = _resolve_model_path(model_path, config_path)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Unable to open camera index {camera_index}")
        return 1
    if camera_width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera_width))
    if camera_height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera_height))

    if display_width is None or display_height is None:
        if fullscreen or windowed_fullscreen:
            screen_w, screen_h = _get_screen_size()
            if screen_w and screen_h:
                display_width = screen_w
                if fullscreen:
                    display_height = screen_h
                else:
                    display_height = max(200, screen_h - windowed_margin)

    if isinstance(landmark_scale, str) and landmark_scale.lower() == "auto":
        landmark_scale_value = 1.0
    else:
        try:
            landmark_scale_value = float(landmark_scale)
        except (TypeError, ValueError):
            landmark_scale_value = 1.0

    if args.calibrate:
        calibrated = _run_calibration(
            camera_index=camera_index,
            backend=backend,
            model_path=str(model_path) if model_path else None,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            mirror=mirror,
            display_width=display_width,
            display_height=display_height,
            overlay_scale=overlay_scale,
            overlay_alpha=overlay_alpha,
            overlay_padding=overlay_padding,
            overlay_line_gap=overlay_line_gap,
            landmark_scale=landmark_scale_value,
            samples_per_step=max(5, int(args.calibration_samples)),
        )
        if not calibrated:
            print("[WARN] Calibration cancelled or failed.")
            return 1
        config.update(calibrated)
        save_config(str(config_path), config)
        print("[INFO] Calibration saved to config.")
        for key, value in calibrated.items():
            print(f"[INFO] {key}: {value:.3f}")
        return 0

    try:
        tracker = HandTracker(
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            backend=backend,
            model_path=str(model_path) if model_path else None,
            landmark_scale=landmark_scale_value,
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        cap.release()
        return 1
    classifier = GestureClassifier(
        thumb_up_down_threshold=thumb_up_down_threshold,
        thumb_extended_ratio=thumb_extended_ratio,
        pinch_ratio=pinch_ratio,
    )
    smoothers = [
        GestureSmoother(
            window_size=window_size,
            min_votes=min_votes,
            min_stable_time=min_stable_time,
            min_frames=min_frames,
            switch_multiplier=switch_multiplier,
            unknown_timeout=unknown_timeout,
        )
        for _ in range(max_num_hands)
    ]
    executor = ActionExecutor(dry_run=args.dry_run)
    log_file = None
    log_active = log_mode in {"active", "all"}
    log_actions = log_mode in {"actions", "active", "all"}
    if log_enabled:
        log_path_resolved = _resolve_log_path(log_path, config_path)
        log_path_resolved.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path_resolved.open("a", encoding="utf-8")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"{timestamp} [INFO] Session started (profile={active_profile})\n")
        log_file.flush()

    def _log_event(message: str) -> None:
        if not log_file:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"{timestamp} {message}\n")
        log_file.flush()

    last_trigger_time = -cooldown_seconds
    last_action = None
    last_logged_active = None
    paused = start_paused

    if not headless:
        cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
        if fullscreen:
            cv2.setWindowProperty(WINDOW_TITLE, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty(WINDOW_TITLE, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
            if display_width and display_height:
                cv2.resizeWindow(WINDOW_TITLE, int(display_width), int(display_height))
                if windowed_fullscreen:
                    cv2.moveWindow(WINDOW_TITLE, 0, 0)

    ui_state = {"controls": [], "action": None}
    profile_index = profile_names.index(active_profile) if active_profile in profile_names else 0

    def _set_profile(index: int) -> None:
        nonlocal active_profile, profile_index
        if not profile_names:
            return
        profile_index = index % len(profile_names)
        active_profile = profile_names[profile_index]
        print(f"[INFO] Active profile: {active_profile}")
        try:
            _log_event(f"[INFO] Profile changed to {active_profile}")
        except NameError:
            pass

    def _reload_runtime_config() -> None:
        nonlocal profiles, profile_names, active_profile, profile_index
        nonlocal cooldown_seconds, smoothers
        nonlocal window_size, min_votes, min_stable_time, min_frames, switch_multiplier, unknown_timeout
        nonlocal log_enabled, log_mode, log_path, log_file, log_active, log_actions
        try:
            new_config = load_config(str(config_path))
        except ValueError as exc:
            print(f"[WARN] Config reload failed: {exc}")
            return

        profiles, profile_names, active_profile = _normalize_profiles(new_config)
        if active_profile not in profiles:
            active_profile = profile_names[0]
        profile_index = profile_names.index(active_profile)

        window_size = int(new_config.get("gesture_window_size", window_size))
        min_votes = int(new_config.get("gesture_min_votes", min_votes))
        min_stable_time = float(new_config.get("gesture_min_stable_time", min_stable_time))
        min_frames = int(new_config.get("gesture_min_frames", min_frames))
        switch_multiplier = float(new_config.get("gesture_switch_multiplier", switch_multiplier))
        unknown_timeout = float(new_config.get("gesture_unknown_timeout", unknown_timeout))
        cooldown_seconds = float(new_config.get("cooldown_seconds", cooldown_seconds))

        classifier.thumb_extended_ratio = float(
            new_config.get("thumb_extended_ratio", classifier.thumb_extended_ratio)
        )
        classifier.pinch_ratio = float(new_config.get("pinch_ratio", classifier.pinch_ratio))
        classifier.thumb_up_down_threshold = float(
            new_config.get("thumb_up_down_threshold", classifier.thumb_up_down_threshold)
        )

        smoothers = [
            GestureSmoother(
                window_size=window_size,
                min_votes=min_votes,
                min_stable_time=min_stable_time,
                min_frames=min_frames,
                switch_multiplier=switch_multiplier,
                unknown_timeout=unknown_timeout,
            )
            for _ in range(max_num_hands)
        ]

        new_log_enabled = bool(new_config.get("log_enabled", log_enabled))
        new_log_mode = str(new_config.get("log_mode", log_mode)).lower()
        new_log_path = str(new_config.get("log_path", log_path))

        if (new_log_enabled != log_enabled) or (new_log_path != log_path):
            if log_file:
                log_file.close()
                log_file = None
        log_enabled = new_log_enabled
        log_mode = new_log_mode
        log_path = new_log_path
        log_active = log_mode in {"active", "all"}
        log_actions = log_mode in {"actions", "active", "all"}

        if log_enabled and log_file is None:
            log_path_resolved = _resolve_log_path(log_path, config_path)
            log_path_resolved.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path_resolved.open("a", encoding="utf-8")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"{timestamp} [INFO] Session resumed (profile={active_profile})\n")
            log_file.flush()

        print("[INFO] Config reloaded.")
        try:
            _log_event("[INFO] Config reloaded")
        except NameError:
            pass

    def _mouse_callback(event, x, y, _flags, userdata):
        if event != cv2.EVENT_LBUTTONUP:
            return
        for item in userdata["controls"]:
            label, (x1, y1, x2, y2), _font_scale, _pad = item
            if x1 <= x <= x2 and y1 <= y <= y2:
                userdata["action"] = label
                return

    if controls_enabled and not headless:
        cv2.setMouseCallback(WINDOW_TITLE, _mouse_callback, ui_state)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[WARN] Camera frame not received")
                break

            if mirror:
                frame = cv2.flip(frame, 1)

            now = time.monotonic()

            hand_landmarks_list, _ = tracker.process(frame)
            hand_landmarks_list = hand_landmarks_list[:max_num_hands]
            if len(hand_landmarks_list) > 1:
                hand_landmarks_list.sort(key=lambda h: h.landmark[0].x)
            display_frame = frame
            if not headless:
                if display_width and display_height:
                    display_frame = cv2.resize(
                        frame,
                        (int(display_width), int(display_height)),
                        interpolation=cv2.INTER_LINEAR
                        if display_width >= frame.shape[1]
                        else cv2.INTER_AREA,
                    )
                if hand_landmarks_list:
                    tracker.draw_landmarks(display_frame, hand_landmarks_list)

            gestures = []
            stable_gestures = []
            for i in range(max_num_hands):
                if i < len(hand_landmarks_list):
                    gesture = classifier.classify(hand_landmarks_list[i])
                else:
                    gesture = GESTURE_UNKNOWN
                gestures.append(gesture)
                stable = smoothers[i].update(gesture, now)
                stable_gestures.append(stable)

            active_gesture = None
            if len(hand_landmarks_list) >= 2:
                left_stable = stable_gestures[0]
                right_stable = stable_gestures[1]
                if left_stable and right_stable:
                    if left_stable == right_stable:
                        active_gesture = f"BOTH_{left_stable}"
                    else:
                        active_gesture = f"DUAL_{left_stable}_{right_stable}"
                elif left_stable:
                    active_gesture = f"LEFT_{left_stable}"
                elif right_stable:
                    active_gesture = f"RIGHT_{right_stable}"
            elif len(hand_landmarks_list) == 1:
                active_gesture = stable_gestures[0]

            action = _resolve_action(active_gesture, profiles, active_profile) if active_gesture else None

            time_since = now - last_trigger_time
            in_cooldown = time_since < cooldown_seconds

            if log_active and active_gesture != last_logged_active:
                _log_event(f"[ACTIVE] {active_gesture or '-'} (profile={active_profile})")
                last_logged_active = active_gesture

            if active_gesture and action and not in_cooldown and not paused:
                executor.trigger(action)
                last_trigger_time = now
                last_action = action
                if log_actions:
                    _log_event(f"[ACTION] gesture={active_gesture} action={action} profile={active_profile}")

            if ui_state["action"]:
                action_label = ui_state["action"]
                ui_state["action"] = None
                if action_label == "X":
                    break
                if action_label == "PROF":
                    _set_profile(profile_index + 1)
                if action_label in {"PAUSE", "RUN"}:
                    paused = not paused
                    state = "PAUSED" if paused else "RUNNING"
                    print(f"[INFO] {state}")
                    if log_enabled:
                        _log_event(f"[INFO] {state}")
                if action_label == "CFG":
                    _reload_runtime_config()
                if action_label in {"FS", "WIN"}:
                    fullscreen = not fullscreen
                    if fullscreen:
                        cv2.setWindowProperty(WINDOW_TITLE, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    else:
                        cv2.setWindowProperty(WINDOW_TITLE, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                        if display_width and display_height:
                            cv2.resizeWindow(WINDOW_TITLE, int(display_width), int(display_height))

            if not headless:
                if isinstance(overlay_scale, str) and overlay_scale.lower() == "auto":
                    font_scale = _auto_overlay_scale(display_frame.shape[0])
                else:
                    try:
                        font_scale = float(overlay_scale)
                    except (TypeError, ValueError):
                        font_scale = 0.7

                thickness = max(1, int(round(font_scale * 2)))
                colors = {
                    "text": (245, 245, 245),
                    "gesture": (0, 255, 255),
                    "ok": (0, 220, 0),
                    "muted": (180, 180, 180),
                    "action": (255, 200, 0),
                    "warn": (0, 165, 255),
                }

                overlay_items = []
                overlay_items.append((f"Profile: {active_profile}", colors["text"]))
                overlay_items.append(
                    (f"Status: {'PAUSED' if paused else 'LIVE'}", colors["warn"] if paused else colors["ok"])
                )
                hand1_present = len(hand_landmarks_list) >= 1
                hand2_present = len(hand_landmarks_list) >= 2
                hand1_gesture = gestures[0] if hand1_present else "-"
                hand1_stable = stable_gestures[0] if hand1_present else None
                overlay_items.append(
                    (f"Left: {hand1_gesture} / {hand1_stable or '-'}", colors["gesture"])
                )
                if max_num_hands > 1:
                    hand2_gesture = gestures[1] if hand2_present else "-"
                    hand2_stable = stable_gestures[1] if hand2_present else None
                    overlay_items.append(
                        (f"Right: {hand2_gesture} / {hand2_stable or '-'}", colors["gesture"])
                    )
                overlay_items.append(
                    (f"Active: {active_gesture or '-'}", colors["ok"] if active_gesture else colors["muted"])
                )
                action_color = colors["muted"] if paused else (colors["action"] if action else colors["muted"])
                overlay_items.append((f"Action: {action or '-'}", action_color))
                if args.dry_run:
                    overlay_items.append(("Mode: DRY-RUN", colors["warn"]))
                if in_cooldown:
                    remaining = max(0.0, cooldown_seconds - time_since)
                    overlay_items.append((f"Cooldown: {remaining:.2f}s", colors["muted"]))
                elif active_gesture and action:
                    overlay_items.append(("Cooldown: ready", colors["ok"]))

                _draw_overlay_panel(
                    display_frame,
                    overlay_items,
                    font_scale=font_scale,
                    thickness=thickness,
                    alpha=overlay_alpha,
                    padding=overlay_padding,
                    line_gap=overlay_line_gap,
                )

                if controls_enabled:
                    pause_label = "RUN" if paused else "PAUSE"
                    button_labels = ["X", "WIN" if fullscreen else "FS", pause_label, "CFG"]
                    if len(profile_names) > 1:
                        button_labels.append("PROF")
                    ui_state["controls"] = _compute_controls(
                        display_frame.shape,
                        button_labels,
                        font_scale=font_scale,
                        thickness=thickness,
                        position=controls_position,
                        scale=controls_scale,
                        margin=controls_margin,
                        gap=controls_gap,
                    )
                    _draw_controls(display_frame, ui_state["controls"], alpha=controls_alpha, thickness=thickness)

                cv2.imshow(WINDOW_TITLE, display_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
                if key in (ord("p"), ord("P")):
                    _set_profile(profile_index + 1)
                if ord("1") <= key <= ord("9"):
                    index = key - ord("1")
                    if index < len(profile_names):
                        _set_profile(index)
                if key in (ord("s"), ord("S")):
                    paused = not paused
                    state = "PAUSED" if paused else "RUNNING"
                    print(f"[INFO] {state}")
                    if log_enabled:
                        _log_event(f"[INFO] {state}")
                if key in (ord("r"), ord("R")):
                    _reload_runtime_config()
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()

    if last_action:
        print(f"[INFO] Last action triggered: {last_action}")
    return 0

# hand_gesture_control (MVP)

Minimal hand gesture control project using a webcam (Windows + Linux).

## What's implemented

- Live webcam preview with landmark overlay and status panel.
- Recognition of multiple single-hand gestures plus two-hand gestures (LEFT/RIGHT/BOTH/DUAL).
- Gesture stabilization (window, time, hysteresis) plus cooldown.
- Gesture-to-key mapping, macros (sequences, text, delay).
- Action profiles and quick switching (UI/keys/CLI).
- Thumb and pinch threshold calibration saved to `config.json`.
- Event logging to a file.
- Headless mode (no window) plus Linux autostart.
- Pause mode and hot config reload.

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Development environment (tests):

```bash
pip install -r requirements-dev.txt
```

## Quick Start

1. Install dependencies (`pip install -r requirements.txt`)
2. Download the model (if you are using Python 3.12/3.13)
3. Run:

```bash
python -m hand_gesture_control --dry-run --backend tasks
```

## Run

```bash
python -m hand_gesture_control
```

Test mode (without sending key presses):

```bash
python -m hand_gesture_control --dry-run
```

Headless mode (runs in the background):

```bash
python -m hand_gesture_control --headless
```

Start paused:

```bash
python -m hand_gesture_control --paused
```

Close the window with `q` or `Esc`.

## MediaPipe backend

By default, `backend=auto`:

- If `mediapipe` provides `solutions`, the app uses the legacy API (simplest setup).
- If `solutions` is not available, it uses `tasks` and requires a `hand_landmarker.task` model.

On Python 3.12/3.13, `mediapipe` usually does not include `solutions`, so you need the model.
Set `task_model_path` in `config.json` (default: `models/hand_landmarker.task`) or pass
`--model`.

Example model download (Linux/macOS):

```bash
mkdir -p models
python - <<'PY'
import pathlib
import urllib.request

url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
path = pathlib.Path("models/hand_landmarker.task")
path.parent.mkdir(parents=True, exist_ok=True)
urllib.request.urlretrieve(url, path)
print("Saved", path)
PY
```

## Configuration

Use the `config.json` file in the project directory.

Most important fields:

- `gesture_to_action`: gesture-to-key mapping
- `gesture_window_size` and `gesture_min_votes`: gesture stabilization
- `gesture_min_stable_time`, `gesture_min_frames`: time and frame count required to accept a gesture
- `gesture_switch_multiplier`: extra hold time when switching gestures
- `gesture_unknown_timeout`: how long to keep the last gesture when the hand disappears
- `thumb_extended_ratio`, `pinch_ratio`, `thumb_up_down_threshold`: classification thresholds
- `cooldown_seconds`: delay between triggers
- `backend`: `auto` / `solutions` / `tasks`
- `task_model_path`: path to `hand_landmarker.task` (for `tasks`)
- `camera_width` / `camera_height`: force camera resolution
- `max_num_hands`: 1 or 2 (default: 2)
- `headless`: `true`/`false` (run without a window)
- `start_paused`: start in paused mode (does not send actions)
- `fullscreen`: `true`/`false` (fullscreen mode)
- `windowed_fullscreen`: `true`/`false` (full-screen-sized window with visible controls)
- `windowed_margin`: how many pixels to subtract from height (for the window bar)
- `display_width` / `display_height`: display size (for example `2880x1800`)
- `overlay_scale`: `auto` or a number (for example `1.0`, `1.2`) for UI scale
- `overlay_alpha`, `overlay_padding`, `overlay_line_gap`: status panel appearance
- `landmark_scale`: hand landmark icon scale (points/lines)
- `controls_enabled`: show on-screen buttons
- `controls_position`: `right` / `top-right` / `top-left`
- `controls_scale`, `controls_alpha`, `controls_margin`, `controls_gap`: on-screen button appearance
- `active_profile`: active profile (for example `default`)
- `profiles`: sets of gesture-to-action mappings
- `log_enabled`: write events to a file
- `log_mode`: `actions` / `active` / `all`
- `log_path`: log file path (for example `logs/gesture_events.log`)

Action examples:

- `SPACE`, `LEFT`, `RIGHT`, `UP`, `DOWN`
- `M`
- `CTRL+SHIFT+P`
- `VOLUME_UP`, `VOLUME_DOWN` (works if the system supports media keys)

Macros (sequences):

- `CTRL+L;TEXT:hello;ENTER`
- `DELAY:0.3;SPACE`

You can also use a JSON list:

```json
"OPEN_PALM": ["CTRL+L", "TEXT:hello", "ENTER"]
```

## Gestures

- `OPEN_PALM`
- `FOUR_FINGERS`
- `FIST`
- `INDEX_UP`
- `TWO_FINGERS`
- `THREE_FINGERS`
- `ROCK` (index + pinky)
- `OK_SIGN`
- `PINCH`
- `THUMB_UP` / `THUMB_DOWN` (or `THUMB` as a fallback)

Two-hand gestures:

- When both hands have the same stable gesture, the active gesture is named `BOTH_<GESTURE>`
  (for example `BOTH_OPEN_PALM`, `BOTH_FIST`).
- When both hands have different gestures: `DUAL_<LEFT>_<RIGHT>` (for example `DUAL_FIST_OPEN_PALM`)
- When only one hand is stable while two hands are visible: `LEFT_<GESTURE>` or `RIGHT_<GESTURE>`

## Profiles

You can define multiple profiles (for example Spotify/YouTube/Presentation).

Example in `config.json`:

```json
"active_profile": "default",
"profiles": {
  "default": {
    "gesture_to_action": { "OPEN_PALM": "SPACE" }
  },
  "spotify": {
    "gesture_to_action": { "OPEN_PALM": "SPACE", "TWO_FINGERS": "LEFT" }
  }
}
```

Profile switching:

- `p` key (cycle)
- `1-9` keys (select profile by order)
- `PROF` on-screen button (if `controls_enabled=true`)
- `--profile <name>` on startup

Quick controls:

- `s` - pause/resume actions
- `r` - hot reload `config.json`

UI buttons:

- `PAUSE` / `RUN` - pause/resume
- `CFG` - reload configuration

## Logging

Enable in `config.json`:

```json
"log_enabled": true,
"log_mode": "actions",
"log_path": "logs/gesture_events.log"
```

## Calibration

Quick threshold calibration (thumb and pinch) with values saved to `config.json`:

```bash
python -m hand_gesture_control --calibrate --backend tasks
```

During calibration:

- show an open hand with the thumb visible
- show a pinch gesture (thumb + index finger)

Abort with `q` or `Esc`.

## Tests

```bash
pytest
```

## Lint/format (optional)

```bash
ruff .
black .
```

## Autostart (Linux)

Scripts in `scripts/`:

```bash
chmod +x scripts/install_autostart_linux.sh
./scripts/install_autostart_linux.sh
```

Remove:

```bash
chmod +x scripts/remove_autostart_linux.sh
./scripts/remove_autostart_linux.sh
```

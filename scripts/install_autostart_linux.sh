#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python not found. Install Python or create .venv first."
  exit 1
fi

mkdir -p "$HOME/.config/autostart"
DESKTOP_FILE="$HOME/.config/autostart/hand_gesture_control.desktop"

cat > "$DESKTOP_FILE" <<EOL
[Desktop Entry]
Type=Application
Name=Hand Gesture Control
Exec=/bin/bash -lc 'cd "$PROJECT_DIR" && "$PYTHON_BIN" -m hand_gesture_control --headless --backend tasks'
X-GNOME-Autostart-enabled=true
EOL

echo "Installed autostart: $DESKTOP_FILE"

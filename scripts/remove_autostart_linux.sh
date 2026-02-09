#!/usr/bin/env bash
set -euo pipefail

DESKTOP_FILE="$HOME/.config/autostart/hand_gesture_control.desktop"
if [[ -f "$DESKTOP_FILE" ]]; then
  rm "$DESKTOP_FILE"
  echo "Removed autostart: $DESKTOP_FILE"
else
  echo "Autostart file not found: $DESKTOP_FILE"
fi

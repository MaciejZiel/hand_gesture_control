import time
from typing import List, Optional, Sequence

from pynput.keyboard import Controller, Key


class ActionExecutor:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._controller = Controller()
        self._key_map = self._build_key_map()

    def trigger(self, action: str | Sequence[str]) -> bool:
        steps = self._normalize_steps(action)
        if not steps:
            return False

        for step in steps:
            if not self._execute_step(step):
                return False
        return True

    def _normalize_steps(self, action: str | Sequence[str]) -> List[str]:
        if not action:
            return []
        if isinstance(action, (list, tuple)):
            return [str(item).strip() for item in action if str(item).strip()]
        action = str(action).strip()
        if not action:
            return []
        normalized = action.replace(",", ";")
        return [part.strip() for part in normalized.split(";") if part.strip()]

    def _execute_step(self, step: str) -> bool:
        if not step:
            return False

        upper = step.upper()
        if upper.startswith("TEXT:"):
            text = step[len("TEXT:") :]
            if self.dry_run:
                print(f"[DRY-RUN] TEXT:{text}")
                return True
            self._controller.type(text)
            return True

        if upper.startswith("DELAY:") or upper.startswith("SLEEP:"):
            value = step.split(":", 1)[1].strip()
            try:
                delay = float(value)
            except ValueError:
                print(f"[WARN] Invalid delay value: {step}")
                return False
            if self.dry_run:
                print(f"[DRY-RUN] DELAY:{delay}")
                return True
            time.sleep(max(0.0, delay))
            return True

        keys = self._parse_action(step)
        if not keys:
            print(f"[WARN] Unknown action mapping: {step}")
            return False

        if self.dry_run:
            print(f"[DRY-RUN] {step}")
            return True

        for key in keys:
            self._controller.press(key)
        for key in reversed(keys):
            self._controller.release(key)
        return True

    def _parse_action(self, action: str) -> Optional[List[object]]:
        tokens = [token.strip().upper() for token in action.split("+") if token.strip()]
        if not tokens:
            return None

        resolved: List[object] = []
        for token in tokens:
            key = self._resolve_token(token)
            if key is None:
                return None
            resolved.append(key)
        return resolved

    def _resolve_token(self, token: str) -> Optional[object]:
        if token in self._key_map:
            return self._key_map[token]

        if len(token) == 1:
            return token.lower()

        if token.startswith("F") and token[1:].isdigit():
            number = int(token[1:])
            if 1 <= number <= 12:
                return getattr(Key, f"f{number}")

        return None

    @staticmethod
    def _build_key_map() -> dict:
        key_map = {
            "SPACE": Key.space,
            "ENTER": Key.enter,
            "RETURN": Key.enter,
            "TAB": Key.tab,
            "ESC": Key.esc,
            "ESCAPE": Key.esc,
            "LEFT": Key.left,
            "RIGHT": Key.right,
            "UP": Key.up,
            "DOWN": Key.down,
            "BACKSPACE": Key.backspace,
            "DELETE": Key.delete,
            "HOME": Key.home,
            "END": Key.end,
            "PAGE_UP": Key.page_up,
            "PAGE_DOWN": Key.page_down,
            "CTRL": Key.ctrl,
            "CONTROL": Key.ctrl,
            "ALT": Key.alt,
            "SHIFT": Key.shift,
            "CMD": Key.cmd,
            "SUPER": Key.cmd,
            "WIN": Key.cmd,
        }

        media_up = getattr(Key, "media_volume_up", None)
        media_down = getattr(Key, "media_volume_down", None)
        media_mute = getattr(Key, "media_volume_mute", None)
        if media_up is not None:
            key_map.update(
                {
                    "VOLUME_UP": media_up,
                    "MEDIA_VOLUME_UP": media_up,
                }
            )
        if media_down is not None:
            key_map.update(
                {
                    "VOLUME_DOWN": media_down,
                    "MEDIA_VOLUME_DOWN": media_down,
                }
            )
        if media_mute is not None:
            key_map.update(
                {
                    "VOLUME_MUTE": media_mute,
                    "MEDIA_VOLUME_MUTE": media_mute,
                }
            )

        return key_map

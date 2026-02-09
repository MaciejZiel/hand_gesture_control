from collections import Counter, deque
import time
from typing import Deque, Optional


class GestureSmoother:
    def __init__(
        self,
        window_size: int = 8,
        min_votes: int = 6,
        min_stable_time: float = 0.2,
        min_frames: int = 4,
        switch_multiplier: float = 1.4,
        unknown_timeout: float = 0.5,
    ) -> None:
        self.window: Deque[str] = deque(maxlen=window_size)
        self.min_votes = min_votes
        self.min_stable_time = min_stable_time
        self.min_frames = min_frames
        self.switch_multiplier = switch_multiplier
        self.unknown_timeout = unknown_timeout
        self._candidate: Optional[str] = None
        self._candidate_since: Optional[float] = None
        self._candidate_frames: int = 0
        self._stable: Optional[str] = None
        self._last_seen_time: Optional[float] = None

    def update(self, gesture: str, now: Optional[float] = None) -> Optional[str]:
        if now is None:
            now = time.monotonic()

        if not gesture:
            gesture = "UNKNOWN"

        self.window.append(gesture)
        if gesture == "UNKNOWN":
            if self._last_seen_time is not None and (now - self._last_seen_time) >= self.unknown_timeout:
                self._candidate = None
                self._candidate_since = None
                self._candidate_frames = 0
                self._stable = None
                self.window.clear()
            return self._stable

        self._last_seen_time = now
        counts = Counter(g for g in self.window if g and g != "UNKNOWN")
        if not counts:
            return self._stable

        best, count = counts.most_common(1)[0]
        if count < self.min_votes:
            return self._stable

        if best != self._candidate:
            self._candidate = best
            self._candidate_since = now
            self._candidate_frames = 1
        else:
            self._candidate_frames += 1

        hold_time = self.min_stable_time
        if self._stable and self._stable != best:
            hold_time *= self.switch_multiplier

        if self._candidate_since is not None:
            if (now - self._candidate_since) >= hold_time and self._candidate_frames >= self.min_frames:
                self._stable = best

        return self._stable

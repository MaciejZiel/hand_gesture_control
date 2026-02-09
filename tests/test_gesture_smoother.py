from hand_gesture_control.gesture_smoother import GestureSmoother


def test_smoother_stabilizes_after_time_and_frames():
    smoother = GestureSmoother(
        window_size=5,
        min_votes=3,
        min_stable_time=0.2,
        min_frames=2,
        switch_multiplier=1.5,
        unknown_timeout=0.5,
    )

    now = 0.0
    assert smoother.update("OPEN_PALM", now) is None
    now += 0.05
    assert smoother.update("OPEN_PALM", now) is None
    now += 0.2
    assert smoother.update("OPEN_PALM", now) == "OPEN_PALM"


def test_smoother_unknown_timeout_resets():
    smoother = GestureSmoother(
        window_size=5,
        min_votes=3,
        min_stable_time=0.1,
        min_frames=2,
        switch_multiplier=1.5,
        unknown_timeout=0.2,
    )

    now = 0.0
    smoother.update("OPEN_PALM", now)
    now += 0.1
    smoother.update("OPEN_PALM", now)
    now += 0.1
    assert smoother.update("OPEN_PALM", now) == "OPEN_PALM"

    now += 0.25
    assert smoother.update("UNKNOWN", now) is None

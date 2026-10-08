"""The background worker keeps the UI responsive: these are its guarantees."""
import time

import pytest

from picore.worker import Worker


def drain(w, timeout=5):
    end, out = time.time() + timeout, []
    while time.time() < end:
        out += list(w.poll())
        if out and not any(w.busy(k) for k in ("a", "b")):
            return out
        time.sleep(0.01)
    return out


def test_result_delivered():
    w = Worker()
    w.submit("a", lambda x: x * 2, 21)
    assert drain(w) == [("a", 42, None)]
    assert not w.busy("a")


def test_latest_job_wins():
    w = Worker()
    w.submit("a", lambda: (time.sleep(0.2), "old")[1])
    w.submit("a", lambda: "new")
    time.sleep(0.4)
    assert [r for _, r, _ in w.poll()] == ["new"]        # the stale answer is dropped


def test_errors_are_captured_not_raised():
    w = Worker()
    w.submit("a", lambda: 1 / 0)
    (kind, result, error), = drain(w)
    assert result is None and isinstance(error, ZeroDivisionError)


def test_cancel_discards_late_result_and_elapsed_tracks_time():
    w = Worker()
    w.submit("b", lambda: (time.sleep(0.2), "late")[1])
    time.sleep(0.05)
    assert w.elapsed("b") >= 0.03      # Windows timers tick every ~15 ms
    w.cancel("b")
    time.sleep(0.3)
    assert list(w.poll()) == []


@pytest.mark.parametrize("working", [
    "check (x+1)^12 -> x^12 + 1",
    "check (x^2+3x-7)^3 -> x^6 + 27x^3 - 343",
    "check d/dx(sin(x)^3 cos(x^2) e^x) -> 3sin(x)^2 cos(x^2) e^x",
    "check ln(x^2 y^3 z) -> ln(x)^2 ln(y)^3 ln(z)",
])
def test_mistake_detective_stays_fast_on_bigger_inputs(working):
    from picore.engine.checker import check
    start = time.monotonic()
    pods = check(working)
    assert time.monotonic() - start < 10, "a single check must stay well under the UI timeout"
    assert any("mistake here" in t for t, _ in pods)

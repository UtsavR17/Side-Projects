"""Unit tests for the what-if engine (pure functions, no DB)."""
import math

import pytest

from app.services.whatif import (
    _avg_win_rate,
    _nearest_bucket,
    _nearest_condition,
    adjusted_prob,
    cond_index,
    fit_score,
)

BUCKETS = {
    "1200-1400": {"runs": 4, "wins": 2, "win_rate": 0.5},
    "1600-1800": {"runs": 3, "wins": 0, "win_rate": 0.0},
    "1800-2000": {"runs": 2, "wins": 1, "win_rate": 0.5},
}
GOINGS = {
    "good": {"runs": 5, "wins": 0, "win_rate": 0.0},
    "good to firm": {"runs": 4, "wins": 2, "win_rate": 0.5},
    "firm": {"runs": 2, "wins": 1, "win_rate": 0.5},
}


class _Snap:
    def __init__(self, by_distance=None, by_track_condition=None):
        self.by_distance = by_distance
        self.by_track_condition = by_track_condition


def test_cond_index_orders_heavy_to_fast():
    assert cond_index("heavy") < cond_index("soft") < cond_index("firm") < cond_index("fast")
    assert cond_index(None) == 3.0


def test_nearest_condition_prefers_exact_match():
    # "good to firm" has its own record; nearest-only would have picked "good"
    assert _nearest_condition(GOINGS, "Good To Firm") == "good to firm"
    assert _nearest_condition(GOINGS, "soft") in {"good", "firm"}  # no exact match -> nearest


def test_nearest_bucket_uses_containing_bucket_then_distance():
    assert _nearest_bucket(BUCKETS, 1700) == "1600-1800"
    assert _nearest_bucket(BUCKETS, 2000) == "1800-2000"
    assert _nearest_bucket(BUCKETS, 1200) == "1200-1400"


def test_avg_win_rate_ignores_single_run_buckets():
    buckets = {
        "a": {"runs": 1, "wins": 1, "win_rate": 1.0},   # ignored (thin record)
        "b": {"runs": 4, "wins": 2, "win_rate": 0.5},
        "c": {"runs": 2, "wins": 0, "win_rate": 0.0},
    }
    assert _avg_win_rate(buckets) == pytest.approx(0.25)


def test_fit_score_is_clamped_and_zero_without_snapshot():
    assert fit_score(None, 1600, "good") == (0.0, 0.0)
    spread = _Snap({
        "1600-1800": {"runs": 5, "wins": 5, "win_rate": 1.0},
        "1200-1400": {"runs": 2, "wins": 0, "win_rate": 0.0},
    })
    # avg = 0.5 -> best bucket gap +0.5 * 3 = 1.5, worst gap -1.5 -> both clamp
    assert fit_score(spread, 1700, None)[0] == 1.0
    assert fit_score(spread, 1300, None)[0] == -1.0


def test_adjusted_prob_moves_toward_stronger_fit():
    snap = _Snap(by_distance=BUCKETS, by_track_condition=GOINGS)
    # 1600m (0% bucket, worst) -> 2000m (50% bucket, best) must raise the chance
    up = adjusted_prob(0.20, snap, 1600, "good", 2000, "good")
    assert up > 0.20
    down = adjusted_prob(0.20, snap, 2000, "good", 1600, "good")
    assert down < 0.20


def test_adjusted_prob_identity_when_context_unchanged():
    snap = _Snap(by_distance=BUCKETS, by_track_condition=GOINGS)
    for prob in (0.05, 0.28411, 0.6, 0.95):
        out = adjusted_prob(prob, snap, 1600, "good to firm", 1600, "good to firm")
        assert out == pytest.approx(prob, abs=1e-9)


def test_adjusted_prob_without_snapshot_is_identity():
    assert adjusted_prob(0.3, None, 1600, "good", 2000, "heavy") == pytest.approx(0.3)


def test_adjusted_prob_hand_calculated_case():
    """Mirrors the worked example in docs/simulator-guide.md §5."""
    snap = _Snap(
        by_distance={
            "1400-1600": {"runs": 7, "wins": 0, "win_rate": 0.0},
            "2000-2200": {"runs": 5, "wins": 1, "win_rate": 0.2},
        },
        by_track_condition={"good to firm": {"runs": 12, "wins": 3, "win_rate": 0.25}},
    )
    base = 0.28411
    # avg distance win rate = 0.1 -> fits -0.3 (1600m) and +0.3 (2000m)
    # -> dlogit = 1.35 * 0.6 = 0.81; going unchanged (exact match) cancels out
    expected = 1 / (1 + math.exp(-(math.log(base / (1 - base)) + 1.35 * 0.6)))
    out = adjusted_prob(base, snap, 1600, "good to firm", 2000, "good to firm")
    assert out == pytest.approx(expected, abs=1e-9)
    # the guide's raw probability before the router renormalises the field
    assert out == pytest.approx(0.4715, abs=1e-4)
    # unchanged context is a strict identity (basis of the UI sanity check)
    assert adjusted_prob(base, snap, 1600, "good to firm", 1600, "good to firm") == pytest.approx(
        base, abs=1e-9
    )

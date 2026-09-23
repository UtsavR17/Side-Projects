"""What-if engine: re-weight stored ensemble probabilities under a changed
race context (distance / track condition). Pure function, no I/O beyond the
snapshots passed in — deliberately heuristic for MVP (documented in README)."""
from __future__ import annotations

import math

from app.models import HorseFormSnapshot

_DISTANCE_WEIGHT = 0.9
_CONDITION_WEIGHT = 0.6
_CONDITION_ORDER = ["heavy", "soft", "good", "good to firm", "firm", "fast"]


def cond_index(cond: str | None) -> float:
    if not cond:
        return 3.0
    c = cond.strip().lower()
    for i, name in enumerate(_CONDITION_ORDER):
        if name in c or c in name:
            return float(i)
    return 3.0


def fit_score(
    snapshot: HorseFormSnapshot | None, distance_m: int | None, condition: str | None
) -> tuple[float, float]:
    """Return (distance_fit, condition_fit) scaled to roughly [-1, 1]."""
    if snapshot is None:
        return 0.0, 0.0
    dist_fit = 0.0
    cond_fit = 0.0
    if distance_m and snapshot.by_distance:
        key = _nearest_bucket(snapshot.by_distance, distance_m)
        if key:
            gap = snapshot.by_distance[key].get("win_rate", 0.0) - _avg_win_rate(
                snapshot.by_distance
            )
            dist_fit = max(-1.0, min(1.0, gap * 3))
    if condition and snapshot.by_track_condition:
        key = _nearest_condition(snapshot.by_track_condition, condition)
        if key:
            gap = snapshot.by_track_condition[key].get("win_rate", 0.0) - _avg_win_rate(
                snapshot.by_track_condition
            )
            cond_fit = max(-1.0, min(1.0, gap * 3))
    return dist_fit, cond_fit


def adjusted_prob(
    base_prob: float,
    snapshot: HorseFormSnapshot | None,
    old_distance: int | None,
    old_condition: str | None,
    new_distance: int | None,
    new_condition: str | None,
) -> float:
    d_new, c_new = fit_score(snapshot, new_distance, new_condition)
    d_old, c_old = fit_score(snapshot, old_distance, old_condition)
    logit = math.log(max(base_prob, 1e-6) / max(1 - base_prob, 1e-6))
    logit += _DISTANCE_WEIGHT * (d_new - d_old) * 1.5
    logit += _CONDITION_WEIGHT * (c_new - c_old) * 1.5
    return 1 / (1 + math.exp(-logit))


def _avg_win_rate(buckets: dict) -> float:
    rates = [b.get("win_rate", 0.0) for b in buckets.values() if b.get("runs", 0) >= 2]
    return sum(rates) / len(rates) if rates else 0.0


def _nearest_bucket(buckets: dict, distance_m: int) -> str | None:
    best, best_gap = None, None
    for key in buckets:
        parsed = key.split("-")
        if len(parsed) != 2:
            continue
        try:
            lo, hi = int(parsed[0]), int(parsed[1])
        except ValueError:
            continue
        gap = 0 if lo <= distance_m <= hi else min(abs(distance_m - lo), abs(distance_m - hi))
        if best_gap is None or gap < best_gap:
            best, best_gap = key, gap
    return best


def _nearest_condition(cond_map: dict, condition: str) -> str | None:
    """Pick the horse's going bucket to use for `condition`.

    An EXACT going match always wins; otherwise fall back to the nearest going
    on the heavy->fast scale (ties resolve to the softer side, i.e. the lower
    index). Exact-first matters because the index scale treats "good" and
    "good to firm" as adjacent, so nearest-only would ignore a horse's actual
    "good to firm" record when it also has a "good" record.
    """
    if not cond_map:
        return None
    target_raw = condition.strip().lower()
    for key in cond_map:
        if str(key).strip().lower() == target_raw:
            return key
    target = cond_index(condition)
    best, best_gap = None, None
    for key in cond_map:
        gap = abs(cond_index(key) - target)
        if best_gap is None or gap < best_gap:
            best, best_gap = key, gap
    return best

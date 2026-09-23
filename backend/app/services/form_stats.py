"""Shared form-statistics helpers used by BOTH the feature-engineering stage
and the ML dataset builder (single definition = no train/serve skew)."""
from __future__ import annotations

CONDITION_ORDER = ["heavy", "soft", "good", "good to firm", "firm", "fast"]
DISTANCE_BUCKET_WIDTH = 200


def distance_bucket(distance_m: int | None) -> str | None:
    if not distance_m:
        return None
    lo = (int(distance_m) // DISTANCE_BUCKET_WIDTH) * DISTANCE_BUCKET_WIDTH
    return f"{lo}-{lo + DISTANCE_BUCKET_WIDTH}"


def condition_index(condition: str | None) -> float:
    if not condition:
        return 3.0
    c = condition.strip().lower()
    for i, name in enumerate(CONDITION_ORDER):
        if name in c or c in name:
            return float(i)
    return 3.0


def form_score(
    runs: int,
    wins: int,
    places: int,
    avg_finish: float | None,
    days_since_last: int | None,
    recent_finishes: list[float] | None = None,
) -> float:
    """0-100 blend: career success + recent trend + freshness.

    recent_finishes: finish positions of the last few starts (worst first? no —
    chronological). Missing values treated as no data (neutral 0.5 components).
    """
    if runs <= 0:
        return 0.0
    win_rate = wins / runs
    place_rate = places / runs

    if recent_finishes:
        last5 = recent_finishes[-5:]
        avg_last = sum(last5) / len(last5)
        # finish 1 -> 1.0, finish 10+ -> ~0.0 (field sizes in MTC are small)
        trend = max(0.0, min(1.0, 1.0 - (avg_last - 1.0) / 9.0))
    else:
        trend = 0.5

    if days_since_last is None:
        recency = 0.5
    elif days_since_last <= 45:
        recency = 1.0
    elif days_since_last >= 150:
        recency = 0.0
    else:
        recency = 1.0 - (days_since_last - 45) / 105.0

    score = 100.0 * (0.45 * win_rate + 0.30 * place_rate + 0.15 * trend + 0.10 * recency)
    return round(score, 2)


def aggregate_stats(finish_positions: list[int | None]) -> dict:
    """Career stats from finish positions (None = unplaced/DN, excluded)."""
    decided = [p for p in finish_positions if p is not None]
    runs = len(decided)
    wins = sum(1 for p in decided if p == 1)
    places = sum(1 for p in decided if p <= 3)
    avg_finish = (sum(decided) / runs) if runs else None
    return {
        "runs": runs,
        "wins": wins,
        "places": places,
        "win_rate": round(wins / runs, 4) if runs else 0.0,
        "place_rate": round(places / runs, 4) if runs else 0.0,
        "avg_finish": round(avg_finish, 2) if avg_finish is not None else None,
    }

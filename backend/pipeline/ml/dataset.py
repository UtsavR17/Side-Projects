"""Leakage-free dataset builder (Prompt C.2/C.3).

Races are streamed in chronological order; each row's features are computed
strictly from history BEFORE that race, then the race's result is ingested.
Distance- and track-condition-specific performance are explicit features (C.3),
as are jockey/trainer strike rates, the joint jockey-trainer combo record
(`combo_runs`/`combo_win_rate`), and a per-venue barrier-draw bias
(`draw_bias`: place rate of this draw third at this venue minus the venue's
overall place rate over prior races).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import RACE_COMPLETED, Race, RaceEntry
from app.services.form_stats import condition_index, distance_bucket, form_score

FEATURE_NAMES = [
    "weight_kg", "barrier", "field_size", "days_since_last",
    "runs", "win_rate", "place_rate", "avg_finish", "form_score",
    "dist_runs", "dist_win_rate", "cond_runs", "cond_win_rate",
    "elo_rating", "jockey_win_rate", "trainer_win_rate",
    "market_prob", "distance_m", "condition_index",
    "combo_runs", "combo_win_rate", "draw_bias",
]

ELO_START = 1500.0
ELO_K = 24.0
# Official ratings are published before the race, so a horse with no race
# history in the DB can be seeded from its rating relative to the field
# instead of sitting at the flat 1500 start. Without this, nomination cards
# (which carry ratings but no odds/jockeys yet) score every runner the same.
ELO_RATING_PER_PT = 6.0


def draw_third(barrier: int | None, field_size: int) -> int | None:
    """0 = inside draw, 1 = middle, 2 = outside — field-relative thirds.

    Field-relative (not fixed 1-3/4-6/7-9) so the bucket means the same thing
    for a 6-horse field and a 16-horse field. None when the draw is unknown.
    """
    if barrier is None or field_size < 2:
        return None
    return min(int((barrier - 1) * 3 / field_size), 2)


def load_races(db: Session, completed_only: bool = True) -> list[Race]:
    query = (
        select(Race)
        .options(
            joinedload(Race.entries).joinedload(RaceEntry.result),
            joinedload(Race.entries).joinedload(RaceEntry.horse),
        )
        .order_by(Race.date.asc())
    )
    if completed_only:
        query = query.where(Race.status == RACE_COMPLETED)
    races = db.scalars(query).unique().all()
    if completed_only:
        races = [r for r in races if any(e.result for e in r.entries)]
    return races


class FeatureBuilder:
    """Maintains per-horse / per-jockey / per-trainer histories + Elo ratings."""

    def __init__(self) -> None:
        self.horse: dict[int, dict] = {}
        self.jockey: dict[int, dict] = {}
        self.trainer: dict[int, dict] = {}
        self.combo: dict[tuple[int, int], dict] = {}
        # venue -> {"thirds": {0/1/2: {"runs", "places"}}, "all": {...}}
        self.barrier: dict[str, dict] = {}

    def _h(self, horse_id: int) -> dict:
        if horse_id not in self.horse:
            self.horse[horse_id] = {
                "runs": 0, "wins": 0, "places": 0, "finishes": [], "last_date": None,
                "elo": ELO_START, "dist": {}, "cond": {},
            }
        return self.horse[horse_id]

    def ratings(self) -> dict[int, float]:
        return {hid: s["elo"] for hid, s in self.horse.items()}

    def race_rows(
        self,
        race: Race,
        entries: list[RaceEntry],
        odds_by_entry: dict[int, float | None] | None = None,
    ) -> list[dict]:
        """Feature rows computed from history strictly BEFORE this race."""
        field = [e for e in entries if not e.scratched]
        n = max(len(field), 1)
        odds_by_entry = odds_by_entry or {}

        inv = {e.id: (1.0 / odds_by_entry[e.id]) for e in field
               if odds_by_entry.get(e.id) and odds_by_entry[e.id] > 1}
        total_inv = sum(inv.values())
        cond_idx = condition_index(race.track_condition)

        rows = []
        rated = [e.rating for e in field if e.rating is not None]
        rating_mean = (sum(rated) / len(rated)) if rated else None
        for e in field:
            st = self._h(e.horse_id)
            days = (race.date - st["last_date"]).days if st["last_date"] else None
            bucket = distance_bucket(race.distance_m)
            d = st["dist"].get(bucket, {"runs": 0, "wins": 0})
            ckey = (race.track_condition or "unknown").lower()
            c = st["cond"].get(ckey, {"runs": 0, "wins": 0})
            avg_finish = (sum(st["finishes"]) / len(st["finishes"])) if st["finishes"] else None
            j = self.jockey.get(e.jockey_id) if e.jockey_id else None
            t = self.trainer.get(e.trainer_id) if e.trainer_id else None
            combo = (self.combo.get((e.jockey_id, e.trainer_id))
                     if e.jockey_id and e.trainer_id else None)
            market = (inv.get(e.id, 0.0) / total_inv) if total_inv > 0 else 1.0 / n

            # Draw bias: place rate of this draw third at this venue vs the
            # venue's overall place rate, over races BEFORE this one.
            draw_bias = 0.0
            third = draw_third(e.barrier, n)
            venue = self.barrier.get(race.venue or "unknown")
            if third is not None and venue and venue["all"]["runs"]:
                bucket = venue["thirds"].get(third)
                if bucket and bucket["runs"]:
                    draw_bias = (bucket["places"] / bucket["runs"]
                                 - venue["all"]["places"] / venue["all"]["runs"])

            # Feature-time Elo: debutants start from their official rating
            # (already known pre-race) rather than a flat 1500.
            elo = st["elo"]
            if st["runs"] == 0 and e.rating is not None and rating_mean is not None:
                elo = ELO_START + (e.rating - rating_mean) * ELO_RATING_PER_PT

            rows.append({
                "horse_id": e.horse_id, "entry_id": e.id,
                "weight_kg": e.weight_kg if e.weight_kg is not None else 55.0,
                "barrier": e.barrier if e.barrier is not None else 6,
                "field_size": n,
                "days_since_last": days if days is not None else 999,
                "runs": st["runs"],
                "win_rate": st["wins"] / st["runs"] if st["runs"] else 0.0,
                "place_rate": st["places"] / st["runs"] if st["runs"] else 0.0,
                "avg_finish": avg_finish if avg_finish is not None else 10.0,
                "form_score": form_score(st["runs"], st["wins"], st["places"], avg_finish,
                                         days, st["finishes"][-5:]),
                "dist_runs": d["runs"],
                "dist_win_rate": d["wins"] / d["runs"] if d["runs"] else 0.0,
                "cond_runs": c["runs"],
                "cond_win_rate": c["wins"] / c["runs"] if c["runs"] else 0.0,
                "elo_rating": elo,
                "jockey_win_rate": (j["wins"] / j["runs"]) if j and j["runs"] else 0.0,
                "trainer_win_rate": (t["wins"] / t["runs"]) if t and t["runs"] else 0.0,
                "market_prob": market,
                "distance_m": race.distance_m if race.distance_m else 1400,
                "condition_index": cond_idx,
                "combo_runs": combo["runs"] if combo else 0,
                "combo_win_rate": (combo["wins"] / combo["runs"])
                                   if combo and combo["runs"] else 0.0,
                "draw_bias": round(draw_bias, 4),
            })
        return rows

    # -------------------------------------------------------------- ingest ---
    def ingest(self, race: Race, entries: list[RaceEntry]) -> None:
        """Fold a race's results into history (called AFTER race_rows)."""
        field = [e for e in entries if not e.scratched]
        n = max(len(field), 1)
        finishes = [(e, e.result.finish_position if e.result else None) for e in field]
        avg_elo = sum(self._h(e.horse_id)["elo"] for e, _ in finishes) / n

        for e, finish in finishes:
            st = self._h(e.horse_id)
            st["runs"] += 1
            place = finish if finish is not None else n
            if finish is not None:
                st["finishes"].append(finish)
                if finish == 1:
                    st["wins"] += 1
                if finish <= 3:
                    st["places"] += 1

            bucket = distance_bucket(race.distance_m)
            if bucket:
                d = st["dist"].setdefault(bucket, {"runs": 0, "wins": 0})
                d["runs"] += 1
                if finish == 1:
                    d["wins"] += 1
            ckey = (race.track_condition or "unknown").lower()
            c = st["cond"].setdefault(ckey, {"runs": 0, "wins": 0})
            c["runs"] += 1
            if finish == 1:
                c["wins"] += 1
            st["last_date"] = race.date

            expected = 1.0 / (1.0 + 10 ** ((avg_elo - st["elo"]) / 400.0))
            actual = (n - place + 1) / n  # win -> 1.0, last -> 1/n, DN ~ last
            st["elo"] += ELO_K * (actual - expected)

            for counter, person_id in ((self.jockey, e.jockey_id), (self.trainer, e.trainer_id)):
                if person_id:
                    pc = counter.setdefault(person_id, {"runs": 0, "wins": 0})
                    pc["runs"] += 1
                    if finish == 1:
                        pc["wins"] += 1

            if e.jockey_id and e.trainer_id:
                pc = self.combo.setdefault((e.jockey_id, e.trainer_id),
                                           {"runs": 0, "wins": 0})
                pc["runs"] += 1
                if finish == 1:
                    pc["wins"] += 1

            third = draw_third(e.barrier, n)
            if third is not None:
                v = self.barrier.setdefault(
                    race.venue or "unknown",
                    {"thirds": {}, "all": {"runs": 0, "places": 0}},
                )
                b = v["thirds"].setdefault(third, {"runs": 0, "places": 0})
                b["runs"] += 1
                v["all"]["runs"] += 1
                if finish is not None and finish <= 3:
                    b["places"] += 1
                    v["all"]["places"] += 1


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------
def build_training_dataset(db: Session) -> tuple[list[dict], list[dict], FeatureBuilder]:
    builder = FeatureBuilder()
    rows: list[dict] = []
    meta: list[dict] = []
    for race in load_races(db, completed_only=True):
        odds = {e.id: e.odds for e in race.entries}
        race_rows = builder.race_rows(race, race.entries, odds)
        for r in race_rows:
            entry = next(e for e in race.entries if e.id == r["entry_id"])
            res = entry.result
            meta.append({
                "race_id": race.id, "horse_id": r["horse_id"],
                "date": race.date.isoformat(),
                "distance_bucket": distance_bucket(race.distance_m),
                "condition": (race.track_condition or "unknown").lower(),
                "finish": res.finish_position if res else None,
                "odds": entry.odds, "field_size": r["field_size"],
            })
        rows.extend(race_rows)
        builder.ingest(race, race.entries)
    return rows, meta, builder


def builder_after_history(db: Session) -> FeatureBuilder:
    """Builder whose state includes ALL completed races (for upcoming predictions)."""
    builder = FeatureBuilder()
    for race in load_races(db, completed_only=True):
        builder.ingest(race, race.entries)
    return builder


def builder_up_to(db: Session, date_iso: str) -> FeatureBuilder:
    """Builder whose state stops before date_iso (time-based holdout, C.2)."""
    builder = FeatureBuilder()
    for race in load_races(db, completed_only=True):
        if race.date.isoformat() >= date_iso:
            break
        builder.ingest(race, race.entries)
    return builder

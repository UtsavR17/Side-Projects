"""Evaluate stage: incremental coverage, boundary-date late imports, upsert."""
from datetime import datetime

from sqlalchemy import select

from app.models import Horse, ModelPerformance, Prediction, Race, RaceEntry, RaceResult
from pipeline.ml.evaluate import stage_evaluate

DAY_ONE = datetime(2026, 5, 10, 14, 0)
OLDER = datetime(2026, 4, 1, 14, 0)


def _make_scored_race(db, race_no: int, when: datetime, winner_correct: bool = True) -> Race:
    """A completed 2-runner race with ensemble predictions stored."""
    race = Race(date=when, race_no=race_no, venue="Champ de Mars", status="completed",
                distance_m=1600, track_condition="good")
    db.add(race)
    db.flush()
    probs = (0.7, 0.3) if winner_correct else (0.3, 0.7)
    for i, prob in enumerate(probs, start=1):
        horse = Horse(name=f"Runner {race_no}-{i}", name_norm=f"runner {race_no} {i}")
        db.add(horse)
        db.flush()
        entry = RaceEntry(race_id=race.id, horse_id=horse.id, barrier=i,
                          weight_kg=55.0, odds=2.0 + i)
        db.add(entry)
        db.flush()
        db.add(RaceResult(race_entry_id=entry.id, finish_position=i))
        db.add(Prediction(race_id=race.id, horse_id=horse.id, model_name="ensemble",
                          win_prob=prob, place_prob=0.5, predicted_rank=i, confidence=0.5))
    db.commit()
    return race


def test_evaluate_scores_and_upserts_without_duplicating(db):
    _make_scored_race(db, 1, DAY_ONE)
    first = stage_evaluate(db)
    assert first["models"]["ensemble"]["races"] == 1
    assert first["models"]["ensemble"]["top1"] == 1.0

    rows = db.scalars(select(ModelPerformance)).all()
    assert len(rows) == 1
    assert rows[0].n_samples == 2

    # a second run must UPDATE the same period, not add a duplicate row
    stage_evaluate(db)
    rows = db.scalars(select(ModelPerformance)).all()
    assert len(rows) == 1
    assert rows[0].n_samples == 2


def test_late_import_on_boundary_date_is_scored(db):
    """A result imported for the last-covered date must still be picked up."""
    _make_scored_race(db, 1, DAY_ONE)
    stage_evaluate(db)

    _make_scored_race(db, 2, DAY_ONE)          # late arrival, same meeting date
    second = stage_evaluate(db)

    assert second["models"]["ensemble"]["races"] == 2   # both races on that date
    rows = db.scalars(select(ModelPerformance)).all()
    assert len(rows) == 1                       # still a single period row...
    assert rows[0].n_samples == 4               # ...now covering both races


def test_older_race_needs_full_rescore(db):
    _make_scored_race(db, 1, DAY_ONE)
    stage_evaluate(db)
    _make_scored_race(db, 3, OLDER)             # back-dated race, already past coverage

    assert stage_evaluate(db)["models"]["ensemble"]["races"] == 1   # boundary day only
    assert db.scalars(select(ModelPerformance)).first().n_samples == 2

    full = stage_evaluate(db, full=True)        # explicit rebuild scores everything
    assert full["models"]["ensemble"]["races"] == 2

    latest = db.scalars(
        select(ModelPerformance).order_by(ModelPerformance.computed_at.desc())
    ).first()
    assert latest.n_samples == 4
    assert latest.period.startswith("2026-04-01")
    assert latest.period.endswith("post-race")


def test_evaluate_skips_when_nothing_to_score(db):
    assert stage_evaluate(db).get("skipped") == "no completed races"

    _make_scored_race(db, 4, DAY_ONE)
    db.query(Prediction).delete()
    db.commit()
    assert stage_evaluate(db).get("skipped") == "no stored predictions to evaluate"

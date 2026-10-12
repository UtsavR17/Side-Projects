"""Full ML cycle on demo data: train -> predict -> explain -> evaluate -> API."""
import pytest
from sqlalchemy import select

from app.models import (
    ModelPerformance, Prediction, PredictionExplanation, RACE_COMPLETED, Race,
)
from seed_demo import build_demo_data


@pytest.fixture()
def seeded(db):
    build_demo_data(db, past_meetings=10, upcoming_meetings=1)
    return db


def test_full_ml_cycle(seeded):
    from pipeline.ml.evaluate import stage_evaluate
    from pipeline.ml.explain import stage_explain
    from pipeline.ml.predict import stage_predict
    from pipeline.ml.train import stage_train

    t = stage_train(seeded)
    assert "trained" in t, t
    assert {"random_forest", "boosting", "elo"} <= set(t["trained"])
    holdouts = seeded.scalars(
        select(ModelPerformance).where(ModelPerformance.period.contains("holdout"))
    ).all()
    assert len(holdouts) == 3
    assert all(h.roc_auc is not None or h.accuracy is not None for h in holdouts)

    p = stage_predict(seeded)
    assert p["races"] == 7, p
    assert p["backfilled"] >= 50, p  # 10 meetings x 7 completed races

    # Ensemble probabilities form a distribution; ranks are a permutation.
    completed = seeded.scalars(
        select(Race).where(Race.status == RACE_COMPLETED).limit(3)
    ).all()
    for race in completed:
        preds = seeded.scalars(
            select(Prediction).where(
                Prediction.race_id == race.id, Prediction.model_name == "ensemble"
            )
        ).all()
        assert len(preds) >= 8
        assert abs(sum(x.win_prob for x in preds) - 1.0) < 0.02
        assert sorted(x.predicted_rank for x in preds) == list(range(1, len(preds) + 1))
        assert all(0.0 <= (x.confidence or 0) <= 1.0 for x in preds)

    e = stage_explain(seeded)
    assert e["predictions_explained"] > 0, e
    dirs = {row.direction for row in seeded.scalars(select(PredictionExplanation)).all()}
    assert "positive" in dirs and "negative" in dirs

    ev = stage_evaluate(seeded)
    assert ev["models"].get("ensemble", {}).get("races", 0) >= 50, ev
    post = seeded.scalars(
        select(ModelPerformance).where(ModelPerformance.period.contains("post-race"))
    ).all()
    assert {m.model_name for m in post} >= {"ensemble", "random_forest", "boosting", "elo"}
    # slices populated (§9)
    ens = next(m for m in post if m.model_name == "ensemble")
    assert ens.by_distance_bucket and ens.by_track_condition


def test_debutant_elo_seeded_from_official_rating(db):
    """Nominations publish ratings before the race; debutants must not all
    score at a flat 1500 (that made every nomination prediction uniform)."""
    from datetime import datetime

    from app.models import Horse, RaceEntry, RACE_SCHEDULED
    from pipeline.ml.dataset import ELO_START, FeatureBuilder

    race = Race(date=datetime(2099, 10, 10, 12, 30), race_no=1, venue="Champ de Mars",
                distance_m=1450, status=RACE_SCHEDULED)
    db.add(race)
    db.flush()
    horses = [Horse(name=n, name_norm=n.lower()) for n in ("ALFA", "BETA", "GAMMA")]
    db.add_all(horses)
    db.flush()
    entries = [
        RaceEntry(race_id=race.id, horse_id=horses[0].id, rating=85, weight_kg=58.0),
        RaceEntry(race_id=race.id, horse_id=horses[1].id, rating=55, weight_kg=58.0),
        RaceEntry(race_id=race.id, horse_id=horses[2].id),          # rating unknown
    ]
    db.add_all(entries)
    db.flush()

    builder = FeatureBuilder()
    rows = {r["horse_id"]: r for r in builder.race_rows(race, entries)}
    top = rows[horses[0].id]["elo_rating"]
    low = rows[horses[1].id]["elo_rating"]
    assert top > ELO_START > low
    assert top - ELO_START == pytest.approx((ELO_START - low))     # symmetric
    assert top == pytest.approx(ELO_START + (85 - 70) * 6.0)       # mean = 70
    assert rows[horses[2].id]["elo_rating"] == ELO_START           # unrated -> flat

    # A field with no ratings at all keeps the classic flat start.
    entries[0].rating = entries[1].rating = None
    flat = builder.race_rows(race, entries)
    assert all(r["elo_rating"] == ELO_START for r in flat)


def test_jockey_trainer_combo_and_draw_bias(db):
    """Combo strike rate + venue draw bias must come only from PRIOR history
    (leakage-free) and stay neutral when there is none."""
    from datetime import datetime

    from app.models import Horse, Jockey, RaceEntry, RaceResult, RACE_COMPLETED, Trainer
    from pipeline.ml.dataset import FEATURE_NAMES, FeatureBuilder, draw_third

    # Field-relative draw thirds (12-horse field: 1-4 inside, 5-8 middle, 9-12 outside)
    assert draw_third(1, 8) == 0 and draw_third(8, 8) == 2
    assert draw_third(4, 12) == 0 and draw_third(5, 12) == 1
    assert draw_third(None, 8) is None and draw_third(3, 1) is None

    jockeys = [Jockey(name=f"J {i}", name_norm=f"j {i}") for i in range(7)]
    trainers = [Trainer(name=f"T {i}", name_norm=f"t {i}") for i in range(7)]
    db.add_all(jockeys + trainers)
    db.flush()
    horses = [Horse(name=f"CB {i}", name_norm=f"cb {i}") for i in range(6)]
    db.add_all(horses)
    db.flush()

    # Prior meeting, barriers 1..6, finishes in barrier order: inside draw
    # (third 0) takes both places, outside (third 2) none. Every entry gets a
    # unique jockey-trainer pair so combo stats are unambiguous.
    prior = Race(date=datetime(2026, 6, 1, 12, 30), race_no=1, venue="Champ de Mars",
                 distance_m=1400, status=RACE_COMPLETED)
    db.add(prior)
    db.flush()
    prior_entries = []
    for i in range(6):
        e = RaceEntry(race_id=prior.id, horse_id=horses[i].id,
                      jockey_id=jockeys[i].id, trainer_id=trainers[i].id,
                      barrier=i + 1, weight_kg=55.0)
        db.add(e)
        db.flush()
        prior_entries.append(e)
    for i, e in enumerate(prior_entries):
        db.add(RaceResult(race_entry_id=e.id, finish_position=i + 1))
    db.commit()

    # Rows for the prior race itself: empty history -> neutral features.
    builder = FeatureBuilder()
    prior_rows = builder.race_rows(prior, prior_entries)
    assert all(r["combo_runs"] == 0 and r["combo_win_rate"] == 0.0 for r in prior_rows)
    assert all(r["draw_bias"] == 0.0 for r in prior_rows)

    builder.ingest(prior, prior_entries)

    # Target race at the same venue two weeks later.
    target = Race(date=datetime(2026, 6, 15, 12, 30), race_no=1, venue="Champ de Mars",
                  distance_m=1400, status="scheduled")
    db.add(target)
    db.flush()
    t_horses = [Horse(name=f"TG {i}", name_norm=f"tg {i}") for i in range(3)]
    db.add_all(t_horses)
    db.flush()
    combos = [(jockeys[0], trainers[0]),   # won together in the prior race
              (jockeys[0], trainers[6]),   # pair never teamed before
              (jockeys[6], trainers[5])]   # pair never teamed before
    t_entries = []
    # 3-horse field: barriers 1/2/3 are thirds 0/1/2.
    for i, (b, (j, t)) in enumerate(zip((1, 2, 3), combos)):
        e = RaceEntry(race_id=target.id, horse_id=t_horses[i].id,
                      jockey_id=j.id, trainer_id=t.id, barrier=b, weight_kg=55.0)
        db.add(e)
        db.flush()
        t_entries.append(e)

    rows = {r["horse_id"]: r for r in builder.race_rows(target, t_entries)}
    a, b_row, c = (rows[h.id] for h in t_horses)
    assert (a["combo_runs"], a["combo_win_rate"]) == (1, 1.0)      # J0+T0 won 1/1
    assert a["draw_bias"] == pytest.approx(0.5)                   # inside: 1.0 - 0.5
    assert (b_row["combo_runs"], b_row["combo_win_rate"]) == (0, 0.0)
    assert b_row["draw_bias"] == pytest.approx(0.0)               # middle: 0.5 - 0.5
    assert c["draw_bias"] == pytest.approx(-0.5)                  # outside: 0.0 - 0.5

    # Every feature row exposes exactly the advertised feature set.
    assert set(FEATURE_NAMES) <= set(a.keys())


def test_predict_backfills_past_scheduled_race_awaiting_results(db):
    """A race whose date has passed but whose results page has not been
    imported yet stays `scheduled` — it must still get leak-free predictions
    so the evaluate stage can score them once the result arrives."""
    from datetime import datetime, timedelta

    from app.models import Horse, RaceEntry
    from pipeline.ml.predict import stage_predict
    from pipeline.ml.train import stage_train

    build_past_meeting(db)  # 7 completed races -> enough history to train

    stale = Race(
        date=datetime.utcnow() - timedelta(days=3), race_no=1,
        venue="Champ de Mars", distance_m=1400, status="scheduled",
    )
    db.add(stale)
    db.flush()
    hs = [Horse(name=f"PS {i}", name_norm=f"ps {i}") for i in range(4)]
    db.add_all(hs)
    db.flush()
    for h in hs:
        db.add(RaceEntry(race_id=stale.id, horse_id=h.id, weight_kg=55.0))
    db.commit()

    assert stage_train(db)["trained"]
    p = stage_predict(db)
    assert p["backfilled"] >= 1, p
    preds = db.scalars(
        select(Prediction).where(
            Prediction.race_id == stale.id, Prediction.model_name == "ensemble"
        )
    ).all()
    assert len(preds) == 4
    assert abs(sum(x.win_prob for x in preds) - 1.0) < 0.02


def build_past_meeting(db):
    from seed_demo import build_demo_data

    build_demo_data(db, past_meetings=1, upcoming_meetings=0)


def test_history_leaderboard_and_simulator_endpoints(client, seeded):
    from pipeline.ml.predict import stage_predict
    from pipeline.ml.train import stage_train

    stage_train(seeded)
    stage_predict(seeded)

    hist = client.get("/api/predictions/history")
    assert hist.status_code == 200
    assert len(hist.json()["history"]) >= 10
    assert "hit" in hist.json()["history"][0]

    board = client.get("/api/leaderboard").json()
    # no post-race rows yet, but holdout rows exist? leaderboard shows all periods
    assert "models" in board

    upcoming = client.get("/api/races").json()["races"]
    race_id = upcoming[0]["id"]
    detail = client.get(f"/api/races/{race_id}").json()
    assert any(e["predictions"] for e in detail["entries"])

    sim = client.post("/api/simulator/what-if",
                      json={"race_id": race_id, "distance_m": 2000})
    assert sim.status_code == 200, sim.text
    body = sim.json()
    assert abs(sum(p["adjusted_win_prob"] for p in body["picks"]) - 1.0) < 0.05
    assert body["picks"] == sorted(body["picks"], key=lambda p: p["rank"])

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

from app.services.form_stats import (
    aggregate_stats, condition_index, distance_bucket, form_score,
)


def test_distance_bucket():
    assert distance_bucket(1200) == "1200-1400"
    assert distance_bucket(1450) == "1400-1600"
    assert distance_bucket(None) is None


def test_condition_index_orders_soft_to_firm():
    assert condition_index("heavy") < condition_index("soft")
    assert condition_index("soft") < condition_index("good")
    assert condition_index("firm") < condition_index("fast")
    assert condition_index(None) == 3.0


def test_form_score_zero_runs():
    assert form_score(0, 0, 0, None, None) == 0.0


def test_form_score_prefers_winners_and_fresh_horses():
    hot = form_score(10, 5, 7, 2.5, 20, [1, 2, 1, 3, 1])
    cold = form_score(10, 1, 3, 7.5, 200, [9, 8, 10, 7, 9])
    assert hot > cold
    assert 0 <= cold < hot <= 100


def test_aggregate_stats_excludes_none():
    stats = aggregate_stats([1, 3, None, 2, 10])
    assert stats["runs"] == 4
    assert stats["wins"] == 1
    assert stats["places"] == 3

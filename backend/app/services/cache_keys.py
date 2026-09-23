"""Central cache-key registry.

The background pipeline calls the invalidate/warm helpers here after writing
new data; the API only ever reads (cache-aside with a TTL as a safety net).
"""

def race_key(race_id: int) -> str:
    return f"race:{race_id}:detail"


def upcoming_key() -> str:
    return "races:upcoming"


def horse_key(horse_id: int) -> str:
    return f"horse:{horse_id}:profile"


def jockey_key(jockey_id: int) -> str:
    return f"jockey:{jockey_id}:profile"


def trainer_key(trainer_id: int) -> str:
    return f"trainer:{trainer_id}:profile"


def leaderboard_key() -> str:
    return "model:leaderboard"


def predictions_history_key(limit: int, offset: int) -> str:
    return f"predictions:history:{limit}:{offset}"


def race_prefix(race_id: int) -> str:
    return f"race:{race_id}:"


def invalidate_for_race(race_id: int) -> None:
    from app.cache import cache

    cache.delete(race_key(race_id), upcoming_key(), leaderboard_key(), predictions_history_key(20, 0))


def invalidate_all_profiles() -> None:
    from app.cache import cache

    for prefix in ("horse:", "jockey:", "trainer:", "race:", "races:", "model:", "predictions:"):
        cache.delete_prefix(prefix)

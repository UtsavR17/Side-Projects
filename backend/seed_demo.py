"""SYNTHETIC DEMO DATA generator — local development & pipeline shake-down only.

Clearly-fictional horses/jockeys/trainers and simulated results. Every row is
tagged "SYNTHETIC DEMO DATA" — this is NOT real MTC form. For real data use
`python -m pipeline.run --stage scrape`.

Usage:  python seed_demo.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import (
    FollowedHorse, Horse, Jockey, NotificationPreference, Race, RaceEntry,
    RaceResult, Trainer, User, RACE_COMPLETED, RACE_SCHEDULED,
)
from app.security import hash_password
from pipeline.features import build_snapshot

NOTE = "SYNTHETIC DEMO DATA"
DISTANCES = [1200, 1400, 1600, 1800, 2000]
CONDITIONS = ["good", "soft", "firm", "good to firm"]
FIRST = ["Demo", "Synth", "Trial", "Sample", "Mock", "Placeholder", "Fiction", "Unit"]
LAST = ["Charger", "Comet", "Dancer", "Echo", "Falcon", "Glider", "Harbor", "Ivory",
        "Jolt", "Kestrel", "Lagoon", "Mirage", "Nimbus", "Orbit", "Pioneer"]
JOCKEY_NAMES = ["A. Test", "B. Sample", "C. Demo", "D. Mock",
                "E. Draft", "F. Mockup", "G. Placeholder", "H. Fake"]
TRAINER_NAMES = ["T. Simulator", "T. Fiction", "T. Example",
                 "T. Practice", "T. Sandbox", "T. Prototype"]


def _next_weekday(base: datetime, weekday: int) -> datetime:
    days = (weekday - base.weekday()) % 7 or 7
    return (base + timedelta(days=days)).replace(hour=14, minute=0, second=0, microsecond=0)


class _DemoWorld:
    """Holds seeded entities + latent abilities used to simulate results."""

    def __init__(self, db, rng: random.Random):
        self.db = db
        self.rng = rng
        self.horses = []
        for i in range(30):
            name = f"{FIRST[i % len(FIRST)]} {LAST[(i * 7 + 3) % len(LAST)]} {i + 1}"
            self.horses.append(Horse(
                name=name, name_norm=name.lower(), sex=rng.choice(["M", "G", "C", "F"]),
                sire="Demo Sire", dam="Demo Dam", foaling_year=2019 + i % 4, notes=NOTE,
            ))
        self.jockeys = [Jockey(name=n, name_norm=n.lower(), license_no=f"J{i + 1:03d}",
                               notes=NOTE)
                        for i, n in enumerate(JOCKEY_NAMES)]
        self.trainers = [Trainer(name=n, name_norm=n.lower(), license_no=f"T{i + 1:03d}",
                                 notes=NOTE)
                         for i, n in enumerate(TRAINER_NAMES)]
        db.add_all(self.horses + self.jockeys + self.trainers)
        db.flush()
        self.ability = {h.id: rng.gauss(0, 1) for h in self.horses}
        self.affinity = {(h.id, d): rng.gauss(0, 0.4)
                         for h in self.horses for d in DISTANCES}
        self.going_aff = {(h.id, c): rng.gauss(0, 0.3)
                          for h in self.horses for c in CONDITIONS}

    def make_race(self, day: datetime, race_no: int, with_results: bool) -> None:
        rng = self.rng
        distance = rng.choice(DISTANCES)
        condition = rng.choice(CONDITIONS)
        race = Race(
            date=day, race_no=race_no, venue="Champ de Mars",
            race_name=f"Demo Plate R{race_no}", distance_m=distance,
            race_class=rng.choice(["Maiden", "Handicap", "Listed"]),
            track_condition=condition, weather="clear",
            status=RACE_COMPLETED if with_results else RACE_SCHEDULED,
            notes=NOTE,
        )
        self.db.add(race)
        self.db.flush()

        field = rng.sample(self.horses, rng.randint(8, 11))
        scored = []
        for horse in field:
            odds = max(1.5, min(18.0, round(28.0 / (2.6 + self.ability[horse.id]), 1)))
            entry = RaceEntry(
                race_id=race.id, horse_id=horse.id,
                jockey_id=rng.choice(self.jockeys).id,
                trainer_id=rng.choice(self.trainers).id,
                barrier=rng.randint(1, len(field)),
                weight_kg=float(rng.randint(53, 58)), odds=odds, notes=NOTE,
            )
            self.db.add(entry)
            self.db.flush()
            if with_results:
                perf = (self.ability[horse.id]
                        + self.affinity[(horse.id, distance)]
                        + self.going_aff[(horse.id, condition)]
                        + rng.gauss(0, 1))
                scored.append((perf, entry))

        if with_results:
            for pos, (_, entry) in enumerate(sorted(scored, key=lambda t: -t[0]), start=1):
                self.db.add(RaceResult(race_entry_id=entry.id, finish_position=pos,
                                       margin=f"{pos - 1}L", time_s=70 + pos * 0.8))


def build_demo_data(db, past_meetings: int = 14, upcoming_meetings: int = 2) -> dict:
    if db.scalar(select(Race).limit(1)) is not None:
        return {"skipped": "database not empty"}

    rng = random.Random(42)
    world = _DemoWorld(db, rng)
    today = datetime.utcnow()

    for m in range(past_meetings):
        meeting_day = _next_weekday(today - timedelta(days=7 * (m + 1)), weekday=5)
        for race_no in range(1, 8):
            world.make_race(meeting_day + timedelta(minutes=40 * race_no),
                            race_no, with_results=True)

    first_up = _next_weekday(today, weekday=5)
    for d in range(upcoming_meetings):
        day = first_up + timedelta(days=d)
        for race_no in range(1, 8):
            world.make_race(day + timedelta(minutes=40 * race_no),
                            race_no, with_results=False)

    # Demo user so follow/notifications are testable out of the box.
    if db.scalar(select(User).where(User.email == "demo@example.com")) is None:
        user = User(email="demo@example.com",
                    password_hash=hash_password("demo1234"),
                    display_name="Demo User")
        db.add(user)
        db.flush()
        db.add(NotificationPreference(user_id=user.id))
        for horse in rng.sample(world.horses, 5):
            db.add(FollowedHorse(user_id=user.id, horse_id=horse.id))

    db.commit()

    # Precompute form snapshots for every horse (feature stage output).
    tomorrow = (today + timedelta(days=1)).date()
    for horse in world.horses:
        build_snapshot(db, horse.id, tomorrow)
    db.commit()

    return {"horses": len(world.horses), "jockeys": len(world.jockeys),
            "trainers": len(world.trainers), "past_meetings": past_meetings,
            "upcoming_meetings": upcoming_meetings, "note": NOTE}


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        result = build_demo_data(db)
        print("Demo data:", result)
        if result.get("skipped"):
            return
        print("\nNext steps:")
        for stage in ("train", "predict", "explain", "evaluate", "warm"):
            print(f"  python -m pipeline.run --stage {stage}")
        print("  uvicorn app.main:app --reload")
    finally:
        db.close()


if __name__ == "__main__":
    main()

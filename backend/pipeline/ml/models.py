"""Base models with a common interface (Prompt C.1).

- RandomForestModel  — robust baseline (always available)
- BoostingModel       — LightGBM when installed, sklearn HistGradientBoosting fallback
- EloModel            — Bradley-Terry rating on top of stored Elo ratings

Each model predicts WIN and PLACE probabilities; artifacts are joblib dicts.
Place target = top-3 finish (documented assumption for MTC field sizes).
"""
from __future__ import annotations

import numpy as np

from pipeline.ml.dataset import FEATURE_NAMES


def to_matrix(rows: list[dict]) -> np.ndarray:
    return np.array(
        [[float(row.get(f, 0.0) or 0.0) for f in FEATURE_NAMES] for row in rows],
        dtype=float,
    )


def _positive_class_proba(estimator, X: np.ndarray) -> np.ndarray:
    proba = estimator.predict_proba(X)
    classes = list(estimator.classes_)
    idx = classes.index(1) if 1 in classes else len(classes) - 1
    return proba[:, idx]


class TreeModel:
    name = "tree"

    def __init__(self, name: str) -> None:
        self.name = name
        self.win = None
        self.place = None

    def _make_win(self):  # pragma: no cover — overridden
        raise NotImplementedError

    def _make_place(self):  # pragma: no cover — overridden
        raise NotImplementedError

    def fit(self, rows: list[dict], y_win: list[int], y_place: list[int]) -> "TreeModel":
        X = to_matrix(rows)
        self.win = self._make_win()
        self.win.fit(X, np.asarray(y_win))
        self.place = self._make_place()
        self.place.fit(X, np.asarray(y_place))
        return self

    def predict_win(self, rows: list[dict]) -> np.ndarray:
        return _positive_class_proba(self.win, to_matrix(rows))

    def predict_place(self, rows: list[dict]) -> np.ndarray:
        return _positive_class_proba(self.place, to_matrix(rows))


class RandomForestModel(TreeModel):
    def __init__(self) -> None:
        super().__init__("random_forest")

    def _make_win(self):
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=300, min_samples_leaf=3, max_features="sqrt",
            random_state=42, n_jobs=-1,
        )

    _make_place = _make_win


class BoostingModel(TreeModel):
    def __init__(self) -> None:
        super().__init__("boosting")

    def _make_win(self):
        try:
            import lightgbm as lgb

            return lgb.LGBMClassifier(
                n_estimators=250, learning_rate=0.05, num_leaves=31,
                random_state=42, verbose=-1,
            )
        except ImportError:
            from sklearn.ensemble import HistGradientBoostingClassifier

            return HistGradientBoostingClassifier(max_iter=200, random_state=42)

    _make_place = _make_win


class EloModel:
    """Rating-based baseline: P(horse) proportional to 10 ** (elo / scale)."""

    name = "elo"
    scale = 200.0

    def __init__(self, ratings: dict[int, float] | None = None) -> None:
        self.ratings = dict(ratings or {})

    def set_ratings(self, ratings: dict[int, float]) -> None:
        self.ratings = dict(ratings)

    def fit(self, rows: list[dict], y_win=None, y_place=None) -> "EloModel":
        # Ratings are learned by FeatureBuilder's chronological replay (dataset.py);
        # train.py injects them via set_ratings before saving the artifact.
        return self

    def _win_probs(self, ratings_list: list[float]) -> np.ndarray:
        arr = np.asarray(ratings_list, dtype=float)
        weights = 10 ** ((arr - arr.mean()) / self.scale)
        return weights / weights.sum()

    def predict_win(self, rows: list[dict]) -> np.ndarray:
        return self._win_probs([self.ratings.get(r["horse_id"], 1500.0) for r in rows])

    def predict_place(self, rows: list[dict]) -> np.ndarray:
        win = self.predict_win(rows)
        return np.minimum(0.98, 1.0 - (1.0 - win) ** 1.8)  # heuristic top-3 conversion


def make_all_models() -> list:
    return [RandomForestModel(), BoostingModel(), EloModel()]

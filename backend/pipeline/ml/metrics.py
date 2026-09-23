"""Shared metric helpers for train-holdout and post-race evaluation (§9)."""
from __future__ import annotations

from math import log


def binary_metrics(y_true: list[int], y_prob: list[float], threshold: float = 0.5) -> dict:
    n = len(y_true)
    if n == 0:
        return {"n_samples": 0}
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / n

    roc_auc = None
    if len(set(y_true)) > 1:
        try:
            from sklearn.metrics import roc_auc_score

            roc_auc = float(roc_auc_score(y_true, y_prob))
        except Exception:  # noqa: BLE001
            roc_auc = None

    eps = 1e-12
    log_loss = -sum(
        t * log(p + eps) + (1 - t) * log(1 - p + eps) for t, p in zip(y_true, y_prob)
    ) / n

    return {
        "n_samples": n,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
        "log_loss": round(log_loss, 4),
    }


def top1_correct(per_race: list[dict]) -> float | None:
    """per_race: [{"probs": [p1..pn], "winner_idx": int|None}, ...]"""
    decided = [r for r in per_race if r["winner_idx"] is not None]
    if not decided:
        return None
    hits = sum(1 for r in decided if max(range(len(r["probs"])), key=lambda i: r["probs"][i])
               == r["winner_idx"])
    return round(hits / len(decided), 4)

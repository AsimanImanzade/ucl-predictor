import numpy as np


def rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean ranked probability score for 3 ordered outcomes (0 home, 1 draw, 2 away).

    Per match: 1/2 * sum_{k=1..2} (cumulative predicted_k - cumulative observed_k)^2.
    """
    probs = np.asarray(probs, dtype=float)
    obs = np.zeros_like(probs)
    obs[np.arange(len(probs)), np.asarray(outcomes, dtype=int)] = 1.0
    diff = np.cumsum(probs, axis=1) - np.cumsum(obs, axis=1)
    return float(np.mean(0.5 * (diff[:, :2] ** 2).sum(axis=1)))

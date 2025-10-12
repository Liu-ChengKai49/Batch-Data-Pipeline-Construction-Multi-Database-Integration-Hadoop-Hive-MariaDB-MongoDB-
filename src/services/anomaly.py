from __future__ import annotations

import statistics
from typing import Any


def mad_outliers(
    rows: list[dict[str, Any]],
    key: str = "close",
    z: float = 3.5,
) -> list[dict[str, Any]]:
    """
    Return rows with a 'mad_score' when |0.6745*(x-median)/MAD| > z.
    """
    xs = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
    if not xs:
        return []
    med = statistics.median(xs)
    devs = [abs(x - med) for x in xs]
    mad = statistics.median(devs)
    if mad == 0:
        return []

    flagged: list[dict[str, Any]] = []
    for r in rows:
        v = r.get(key)
        if isinstance(v, (int, float)):
            score = 0.6745 * abs(float(v) - med) / mad
            if score > z:
                flagged.append({**r, "mad_score": float(score)})
    return flagged

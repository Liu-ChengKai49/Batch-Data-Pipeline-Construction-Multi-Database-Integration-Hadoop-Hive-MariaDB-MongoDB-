# src/services/signals.py
from __future__ import annotations

from typing import Any, Optional


def moving_average(
    rows: list[dict[str, Any]],
    key: str = "close",
    window: int = 5,
    out_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    out_key = out_key or f"ma_{window}"
    buf: list[float | None] = []
    out: list[dict[str, Any]] = []

    for r in rows:
        v = r.get(key)
        buf.append(float(v) if isinstance(v, (int, float)) else None)
        if len(buf) >= window and all(x is not None for x in buf[-window:]):
            ma = sum(x for x in buf[-window:] if x is not None) / window
        else:
            ma = None
        out.append({**r, out_key: ma})  # <-- fixed
    return out

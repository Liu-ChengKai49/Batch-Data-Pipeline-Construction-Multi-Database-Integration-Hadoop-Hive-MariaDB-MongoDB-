# src/services/signals.py
from fastapi import APIRouter, HTTPException
from ..deps import to_json
from services.prices import fetch_prices
from services.signals import moving_average as ma_calc

router = APIRouter()

@router.get("/signals/moving_average")
def get_ma(symbol: str, start: str | None = None, end: str | None = None):
    try:
        df = fetch_prices(symbol, start, end, limit=5000)
        out = ma_calc(df, windows=(5, 20, 60))
        return to_json(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"signals.moving_average failed: {type(e).__name__}: {e}")


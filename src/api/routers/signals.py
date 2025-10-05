from fastapi import APIRouter, Query
from ..deps import to_json
from ...services.prices import fetch_prices
from ...services.signals import moving_average
router = APIRouter()

@router.get("/signals/moving_average")
def get_ma(symbol: str, start: str|None=None, end: str|None=None):
    df = fetch_prices(symbol, start, end, limit=5000)
    out = moving_average(df, windows=(5,20,60))
    return to_json(out)
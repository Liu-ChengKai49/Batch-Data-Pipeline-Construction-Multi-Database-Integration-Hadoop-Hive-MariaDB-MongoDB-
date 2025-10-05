from fastapi import APIRouter, Query
from ..deps import to_json
from services.prices import fetch_prices
router = APIRouter()

@router.get("/prices")
def get_prices(symbol: str = Query(..., example="2330.tw"),
               start: str|None=None, end: str|None=None, limit: int = 500):
    df = fetch_prices(symbol, start, end, limit)
    return to_json(df)
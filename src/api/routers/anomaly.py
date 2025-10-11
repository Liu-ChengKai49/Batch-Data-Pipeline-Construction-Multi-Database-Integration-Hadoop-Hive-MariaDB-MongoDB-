from fastapi import APIRouter

from services.anomaly import mad_outliers
from services.prices import fetch_prices

from ..deps import to_json

router = APIRouter()

@router.get("/anomaly")
def anomaly(symbol: str, method: str = "mad", start: str|None=None, end: str|None=None):
    df = fetch_prices(symbol, start, end, limit=5000)
    if method.lower()=="mad":
        out = mad_outliers(df, col="close", z=3.5)
        return to_json(out)
    return {"error":"unsupported method"}
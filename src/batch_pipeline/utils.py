from pydantic import BaseModel, Field


class PriceRow(BaseModel):
    symbol: str
    dt: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(ge=0)

def clamp_close(row: PriceRow) -> float:
    return max(row.low, min(row.close, row.high))

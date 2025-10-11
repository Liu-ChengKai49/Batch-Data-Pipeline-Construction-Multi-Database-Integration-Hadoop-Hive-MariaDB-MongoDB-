# src/api/main.py
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .routers.anomaly import router as anomaly_router

# ⬇️ import the routers directly as objects
from .routers.health import router as health_router
from .routers.prices import router as prices_router
from .routers.signals import router as signals_router

app = FastAPI(title="TW Stocks API", version="0.1.0")

REQ_LAT = Histogram("api_request_latency_seconds", "latency", ["route","method","code"])
REQ_CNT = Counter("api_requests_total", "requests", ["route","method","code"])
DQ_FAILS = Gauge("dq_failures_total", "Number of last DQ failures")

@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    resp = await call_next(request)
    rt = request.url.path or "/"
    code = resp.status_code
    REQ_LAT.labels(rt, request.method, code).observe(time.perf_counter()-start)
    REQ_CNT.labels(rt, request.method, code).inc()
    return resp

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ⬇️ include the router objects
app.include_router(health_router)
app.include_router(prices_router)
app.include_router(signals_router)
app.include_router(anomaly_router)

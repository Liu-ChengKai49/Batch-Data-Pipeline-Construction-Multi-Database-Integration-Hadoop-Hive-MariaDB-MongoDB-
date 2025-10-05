# src/api/main.py
import time
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from .routers import prices, signals, anomaly, health

app = FastAPI(title="TW Stocks API", version="0.1.0")

REQ_LAT = Histogram("api_request_latency_seconds", "latency", ["route","method","code"])
REQ_CNT = Counter("api_requests_total", "requests", ["route","method","code"])
DQ_FAILS = Gauge("dq_failures_total", "Number of last DQ failures")  # you can set it from DQ script (optional)

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

app.include_router(health.router)
app.include_router(prices.router)
app.include_router(signals.router)
app.include_router(anomaly.router)
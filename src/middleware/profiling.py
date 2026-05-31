import os
import time
from collections import defaultdict
from pyinstrument import Profiler
from fastapi import Request

PROFILING_ENABLED = os.getenv("PROFILING_ENABLED", "false").lower() == "true"
PROFILING_INTERVAL = 0.001

_stats = defaultdict(lambda: {
    "count": 0,
    "total_ms": 0.0,
    "min_ms": float("inf"),
    "max_ms": 0.0,
    "errors": 0,
})

def record_request(method: str, path: str, duration_ms: float, status_code: int):
    key = f"{method} {path}"
    s = _stats[key]
    s["count"] += 1
    s["total_ms"] += duration_ms
    s["min_ms"] = min(s["min_ms"], duration_ms)
    s["max_ms"] = max(s["max_ms"], duration_ms)
    if status_code >= 400:
        s["errors"] += 1

def get_stats():
    result = {}
    for key, s in _stats.items():
        method = key.split(" ")[0]
        result[key] = {
            "method": method,
            "count": s["count"],
            "avg_ms": round(s["total_ms"] / s["count"], 2) if s["count"] else 0,
            "min_ms": round(s["min_ms"], 2) if s["min_ms"] != float("inf") else 0,
            "max_ms": round(s["max_ms"], 2),
            "errors": s["errors"],
            "error_rate": f"{round(s['errors'] / s['count'] * 100, 1)}%" if s["count"] else "0%",
        }
    return result

async def profiling_middleware(request: Request, call_next):
    should_profile = PROFILING_ENABLED or request.query_params.get("profile") == "1"
    start = time.perf_counter()

    if not should_profile:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        record_request(request.method, request.url.path, duration_ms, response.status_code)
        return response

    profiler = Profiler(interval=PROFILING_INTERVAL, async_mode="enabled")
    profiler.start()
    response = await call_next(request)
    profiler.stop()
    duration_ms = (time.perf_counter() - start) * 1000
    record_request(request.method, request.url.path, duration_ms, response.status_code)

    print(f"\n Profile for {request.method} {request.url.path}")
    print(profiler.output_text(unicode=True, color=True))
    return response
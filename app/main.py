import logging
from collections import defaultdict, deque
from pathlib import Path
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.browse import router as browse_router
from app.api.calendar import router as calendar_router
from app.api.control import router as control_router
from app.api.corrections import router as corrections_router
from app.api.debug import router as debug_router
from app.api.emphasis import router as emphasis_router
from app.api.generation import router as generation_router
from app.api.health import router as health_router
from app.api.ingestion import router as ingestion_router
from app.api.mapping import router as mapping_router
from app.api.mastery import router as mastery_router
from app.api.planning import router as planning_router
from app.api.studio import router as studio_router
from app.planning.scheduler import InfeasibleScheduleError
from app.workers.ingestion import router as jobs_router

app = FastAPI(title="EduFlow")
REQUEST_HISTORY: defaultdict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = uuid4().hex
    start = monotonic()
    if request.method == "POST" and request.url.path.startswith(
        ("/planning", "/generation", "/ingestion", "/demo", "/studio")
    ):
        client = request.client.host if request.client else "unknown"
        for key in list(REQUEST_HISTORY):
            if not REQUEST_HISTORY[key] or start - REQUEST_HISTORY[key][-1] > 60:
                REQUEST_HISTORY.pop(key, None)
        if client not in REQUEST_HISTORY and len(REQUEST_HISTORY) >= 1000:
            return JSONResponse(
                status_code=429,
                content={"detail": "Request capacity reached"},
                headers={"Retry-After": "60"},
            )
        history = REQUEST_HISTORY[client]
        while history and start - history[0] > 60:
            history.popleft()
        if len(history) >= 120:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests; retry in one minute"},
                headers={"Retry-After": "60"},
            )
        history.append(start)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    elapsed = (monotonic() - start) * 1000
    response.headers["Server-Timing"] = f"app;dur={elapsed:.1f}"
    logging.getLogger(__name__).info(
        "request id=%s method=%s status=%s elapsed_ms=%.1f",
        request_id,
        request.method,
        response.status_code,
        elapsed,
    )
    return response


@app.exception_handler(InfeasibleScheduleError)
async def infeasible_plan(request: Request, exc: InfeasibleScheduleError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(calendar_router)
app.include_router(mapping_router)
app.include_router(mastery_router)
app.include_router(emphasis_router)
app.include_router(planning_router)
app.include_router(corrections_router)
app.include_router(generation_router)
app.include_router(browse_router)
app.include_router(debug_router)
app.include_router(studio_router)
app.include_router(control_router)
app.include_router(jobs_router)

# Minimal demo UI. Mounted last so it doesn't shadow any API route above.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")

"""
API local OptiLag — http://127.0.0.1:8765

  python -m optilag_backend.api
  Docs: http://127.0.0.1:8765/docs
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import asynccontextmanager
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from optilag_backend.config import settings
from optilag_backend.exceptions import OptiLagError, ProbeError, RouteNotFoundError
from optilag_backend.logging_config import setup_logging, get_logger
from optilag_backend.services import get_services
from optilag_backend.models import (
    EngineAction,
    EngineActionType,
    ProbeOut,
    EngineOut,
    MetricsOut,
    RouteCompareOut,
    StatsOut,
    SessionOut,
    HealthOut,
    probe_from_backend,
)

setup_logging(settings.log_level, settings.log_json)
log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    svc = get_services()
    svc.start_background()
    log.info(
        "API up host=%s port=%s version=%s",
        settings.api_host,
        settings.api_port,
        settings.version,
    )
    yield
    svc.stop_background()
    log.info("API shutdown")


app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.version,
    description=(
        "Backend local profissional: probes UDP/TCP, rotas BGP vs overlay, "
        "motor de sessão, persistência SQLite."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(OptiLagError)
async def optilag_error_handler(request: Request, exc: OptiLagError):
    return JSONResponse(
        status_code=400,
        content={"ok": False, "code": exc.code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("unhandled %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "code": "internal_error", "message": "Erro interno"},
    )


def _svc():
    return get_services()


@app.get("/", tags=["meta"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    return HealthOut(ok=True, ts=time.time())


@app.get("/probe", response_model=ProbeOut, tags=["network"])
def probe_now() -> ProbeOut:
    return _svc().probe_now()


@app.get("/probe/history", tags=["network"])
def probe_history(limit: int = 50):
    limit = max(1, min(limit, 500))
    svc = _svc()
    return {
        "items": svc.db.recent_probes(limit),
        "live": svc.sampler.series_combined(),
    }


@app.get("/routes", tags=["routing"])
def list_routes():
    return {"routes": _svc().list_routes()}


@app.get("/routes/best", response_model=RouteCompareOut, tags=["routing"])
def best_route() -> RouteCompareOut:
    c = _svc().router.best_overlay()
    return RouteCompareOut(
        name=c.name,
        bgp_path=c.bgp_path,
        overlay_path=c.overlay_path,
        bgp_as=getattr(c, "bgp_as", []) or [],
        bgp_ping_est=c.bgp_ping_est,
        overlay_ping_est=c.overlay_ping_est,
        gain_ms=c.gain_ms,
        hops=getattr(c, "overlay_hops", []) or [],
        algorithm=getattr(c, "algorithm", "dijkstra"),
    )


@app.get("/routes/{name}", response_model=RouteCompareOut, tags=["routing"])
def compare_route(name: str, optimized: bool = True) -> RouteCompareOut:
    from optilag_backend.routing.simulator import ROUTE_PROFILES

    if name not in ROUTE_PROFILES:
        raise HTTPException(status_code=404, detail=f"Rota desconhecida: {name}")
    c = _svc().router.choose(name, optimized=optimized)
    # choose returns RouteChoice — map fields
    return RouteCompareOut(
        name=getattr(c, "name", name),
        bgp_path=getattr(c, "bgp_path", "") or "",
        overlay_path=getattr(c, "overlay_path", "") or "",
        bgp_as=getattr(c, "bgp_as", []) or [],
        bgp_ping_est=int(getattr(c, "bgp_ping_est", 0) or 0),
        overlay_ping_est=int(getattr(c, "overlay_ping_est", 0) or 0),
        gain_ms=int(getattr(c, "gain_ms", 0) or 0),
        hops=getattr(c, "overlay_hops", []) or [],
        algorithm=getattr(c, "algorithm", "dijkstra"),
    )


@app.get("/engine", response_model=EngineOut, tags=["engine"])
def engine_status() -> EngineOut:
    engine = _svc().engine
    sampler = _svc().sampler
    m = engine.metrics
    nested = probe_from_backend(engine.last_probe) if engine.last_probe else None
    return EngineOut(
        state=engine.state.value,
        route=engine.route_name,
        competitive=engine.competitive,
        metrics=MetricsOut(
            ping=m.ping,
            loss=m.loss,
            jitter=m.jitter,
            quality=m.quality,
            ping_before=m.ping_before,
        ),
        session_seconds=engine.session_seconds(),
        last_probe=engine.last_probe.summary() if engine.last_probe else None,
        probe=nested,
    )


@app.post("/engine", response_model=EngineOut, tags=["engine"])
def engine_control(body: EngineAction) -> EngineOut:
    svc = _svc()
    engine = svc.engine
    sampler = svc.sampler

    if body.route:
        engine.set_route(body.route)
    if body.competitive is not None:
        engine.competitive = body.competitive

    if body.action == EngineActionType.start:
        if sampler.last:
            engine.last_probe = sampler.last
        engine.start()
        log.info("engine start route=%s", engine.route_name)
    elif body.action == EngineActionType.stop:
        started = engine.session_started or time.time()
        before = engine.metrics.ping_before
        after = engine.metrics.ping
        route = engine.route_name
        engine.stop()
        try:
            svc.db.save_session(
                started=started,
                ended=time.time(),
                route=route,
                ping_before=before,
                ping_after=after,
            )
        except Exception as e:
            log.warning("save_session: %s", e)
        log.info("engine stop route=%s", route)
    elif body.action == EngineActionType.tick:
        if sampler.last:
            engine.last_probe = sampler.last
        engine.tick()

    return engine_status()


@app.get("/sessions", response_model=List[SessionOut], tags=["data"])
def sessions(limit: int = 30) -> List[SessionOut]:
    limit = max(1, min(limit, 200))
    rows = _svc().db.recent_sessions(limit)
    out = []
    for r in rows:
        try:
            out.append(SessionOut(**dict(r)))
        except Exception:
            continue
    return out


@app.get("/stats", response_model=StatsOut, tags=["data"])
def stats() -> StatsOut:
    s = _svc().db.stats()
    return StatsOut(**s)


@app.post("/export", tags=["data"])
def export_data():
    path = os.path.join(os.path.dirname(__file__), f"export_{int(time.time())}.json")
    _svc().db.export_json(path)
    return {"path": path}


def main():
    import uvicorn

    uvicorn.run(
        "optilag_backend.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

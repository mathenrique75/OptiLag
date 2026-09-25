"""API local FastAPI — http://127.0.0.1:8765

  pip install fastapi uvicorn
  python -m optilag_backend.api
"""
from __future__ import annotations

import os
import sys
import time
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    print("Instala: pip install fastapi uvicorn")
    raise

from optilag_backend.network.probes import multi_probe
from optilag_backend.network.sampler import ProbeSampler
from optilag_backend.routing.simulator import RouteSimulator, ROUTE_PROFILES
from optilag_backend.core.engine import OptimizationEngine
from optilag_backend.persistence import Persistence
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
    dump_public,
)

app = FastAPI(
    title="OptiLag API",
    version="0.3.0",
    description="Backend local: probes UDP/TCP, rotas BGP vs overlay, motor de sessão.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Persistence()
engine = OptimizationEngine()
router = RouteSimulator()
sampler = ProbeSampler(interval=5.0, history=120, on_result=lambda p: db.save_probe(p))
sampler.start()


@app.get("/", tags=["meta"])
def root():
    return {"app": "OptiLag", "version": "0.3.0", "docs": "/docs"}


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    return HealthOut(ok=True, ts=time.time())


@app.get("/probe", response_model=ProbeOut, tags=["network"])
def probe_now() -> ProbeOut:
    result = multi_probe()
    db.save_probe(result)
    engine.last_probe = result
    return probe_from_backend(result)


@app.get("/probe/history", tags=["network"])
def probe_history(limit: int = 50):
    return {"items": db.recent_probes(limit), "live": sampler.series_combined()}


@app.get("/routes", tags=["routing"])
def list_routes():
    return {"routes": list(ROUTE_PROFILES.keys())}


@app.get("/routes/best", response_model=RouteCompareOut, tags=["routing"])
def best_route() -> RouteCompareOut:
    c = router.best_overlay()
    return RouteCompareOut(
        name=c.name,
        bgp_path=c.bgp_path,
        overlay_path=c.overlay_path,
        bgp_as=c.bgp_as,
        bgp_ping_est=c.bgp_ping_est,
        overlay_ping_est=c.overlay_ping_est,
        gain_ms=c.gain_ms,
        hops=c.overlay_hops,
        algorithm=c.algorithm,
    )


@app.get("/routes/{name}/compare", response_model=RouteCompareOut, tags=["routing"])
def compare_route(name: str, optimized: bool = True) -> RouteCompareOut:
    match = name if name in ROUTE_PROFILES else next(
        (k for k in ROUTE_PROFILES if name.lower() in k.lower()), None
    )
    if not match:
        raise HTTPException(404, "Rota desconhecida")
    real = sampler.last.combined if sampler.last else None
    c = router.choose(match, real_ping=real, optimized=optimized)
    return RouteCompareOut(
        name=c.name,
        bgp_path=c.bgp_path,
        overlay_path=c.overlay_path,
        bgp_as=c.bgp_as,
        bgp_ping_est=c.bgp_ping_est,
        overlay_ping_est=c.overlay_ping_est,
        gain_ms=c.gain_ms,
        hops=c.overlay_hops,
        algorithm=c.algorithm,
    )


@app.get("/engine", response_model=EngineOut, tags=["engine"])
def engine_status() -> EngineOut:
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
    if body.route:
        engine.set_route(body.route)
    if body.competitive is not None:
        engine.competitive = body.competitive

    if body.action == EngineActionType.start:
        if sampler.last:
            engine.last_probe = sampler.last
        engine.start()
    elif body.action == EngineActionType.stop:
        started = engine.session_started or time.time()
        before = engine.metrics.ping_before
        after = engine.metrics.ping
        engine.stop()
        db.save_session(
            started=started,
            ended=time.time(),
            route=engine.route_name,
            ping_before=before,
            ping_after=after,
        )
    elif body.action == EngineActionType.tick:
        if sampler.last:
            engine.last_probe = sampler.last
        engine.tick()

    return engine_status()


@app.get("/sessions", response_model=List[SessionOut], tags=["data"])
def sessions(limit: int = 30) -> List[SessionOut]:
    rows = db.recent_sessions(limit)
    return [SessionOut(**r) for r in rows]


@app.get("/stats", response_model=StatsOut, tags=["data"])
def stats() -> StatsOut:
    s = db.stats()
    return StatsOut(**s)


@app.post("/export", tags=["data"])
def export_data():
    path = os.path.join(os.path.dirname(__file__), f"export_{int(time.time())}.json")
    db.export_json(path)
    return {"path": path}


def main():
    import uvicorn
    uvicorn.run("optilag_backend.api:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()

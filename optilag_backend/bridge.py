"""Ponte UI ↔ backend. A interface importa daqui em vez de duplicar lógica."""
from __future__ import annotations

import os
import sys

# artifacts/ no path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from optilag_backend.network.probes import multi_probe, ProbeResult
from optilag_backend.network.sampler import ProbeSampler
from optilag_backend.routing.simulator import RouteSimulator, ROUTE_PROFILES
from optilag_backend.core.engine import OptimizationEngine, EngineState
from optilag_backend.persistence import Persistence

# Singletons partilhados pela UI
db = Persistence()
engine = OptimizationEngine()
router = RouteSimulator()
_sampler: ProbeSampler | None = None


def get_sampler() -> ProbeSampler:
    global _sampler
    if _sampler is None:
        def _on(p: ProbeResult):
            try:
                db.save_probe(p)
                engine.last_probe = p
            except Exception:
                pass
        _sampler = ProbeSampler(interval=5.0, history=60, on_result=_on)
        _sampler.start()
    return _sampler


def probe_now() -> ProbeResult:
    result = multi_probe()
    try:
        db.save_probe(result)
    except Exception:
        pass
    engine.last_probe = result
    return result


def measure_combined() -> int | None:
    """Compatível com o antigo _measure_ping da UI."""
    r = probe_now()
    return r.combined


def route_compare(name: str, optimized: bool = False):
    real = engine.last_probe.combined if engine.last_probe else None
    return router.choose(name, real_ping=real, optimized=optimized)


def start_optimization(route: str, competitive: bool = False):
    engine.route_name = route
    engine.competitive = competitive
    if engine.last_probe is None:
        probe_now()
    engine.start()
    return engine


def stop_optimization(game: str = "", user: str = ""):
    started = engine.session_started or 0
    before = engine.metrics.ping_before
    after = engine.metrics.ping
    route = engine.route_name
    engine.stop()
    if started:
        import time
        try:
            db.save_session(
                started=started,
                ended=time.time(),
                route=route,
                game=game,
                user=user,
                ping_before=before,
                ping_after=after,
            )
        except Exception:
            pass
    return engine


def tick():
    if get_sampler().last:
        engine.last_probe = get_sampler().last
    return engine.tick()

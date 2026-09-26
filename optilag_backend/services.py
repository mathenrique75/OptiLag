"""Camada de serviços — orquestra probes, rotas, engine e DB."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from optilag_backend.config import settings
from optilag_backend.exceptions import ProbeError, RouteNotFoundError
from optilag_backend.logging_config import get_logger
from optilag_backend.network.probes import multi_probe
from optilag_backend.network.sampler import ProbeSampler
from optilag_backend.routing.simulator import RouteSimulator, ROUTE_PROFILES
from optilag_backend.core.engine import OptimizationEngine
from optilag_backend.persistence import Persistence
from optilag_backend.models import ProbeOut, RouteCompareOut, probe_from_backend

log = get_logger("services")


class BackendServices:
    """Facade única para API e bridge UI."""

    def __init__(self) -> None:
        self.db = Persistence(str(settings.db_path))
        self.engine = OptimizationEngine()
        self.router = RouteSimulator()
        self.sampler = ProbeSampler(
            interval=settings.sampler_interval_sec,
            history=settings.sampler_history,
            on_result=lambda p: self._on_probe(p),
        )
        self._sampler_started = False
        log.info("BackendServices init db=%s", settings.db_path)

    def _on_probe(self, p: Any) -> None:
        try:
            self.db.save_probe(p)
        except Exception as e:
            log.warning("save_probe falhou: %s", e)

    def start_background(self) -> None:
        if not self._sampler_started:
            self.sampler.start()
            self._sampler_started = True
            log.info("sampler iniciado interval=%.1fs", settings.sampler_interval_sec)

    def stop_background(self) -> None:
        if self._sampler_started:
            try:
                self.sampler.stop()
            except Exception:
                pass
            self._sampler_started = False
            log.info("sampler parado")

    def probe_now(self) -> ProbeOut:
        try:
            result = multi_probe()
        except Exception as e:
            log.exception("probe")
            raise ProbeError(str(e)) from e
        try:
            self.db.save_probe(result)
        except Exception as e:
            log.warning("persist probe: %s", e)
        self.engine.last_probe = result
        return probe_from_backend(result)

    def list_routes(self) -> List[str]:
        return list(ROUTE_PROFILES.keys())

    def stats(self) -> Dict[str, Any]:
        return self.db.stats()

    def recent_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.db.recent_sessions(limit)


_services: Optional[BackendServices] = None


def get_services() -> BackendServices:
    global _services
    if _services is None:
        _services = BackendServices()
    return _services

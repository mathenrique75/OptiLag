"""Motor de sessão de otimização (estado + métricas simuladas sobre probes reais)."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..network.probes import ProbeResult, multi_probe
from ..routing.simulator import RouteChoice, RouteSimulator


class EngineState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    OPTIMIZING = "optimizing"
    STOPPED = "stopped"


@dataclass
class EngineMetrics:
    ping: int = 0
    loss: float = 0.0
    jitter: int = 0
    ping_before: int = 0
    quality: str = "—"


@dataclass
class OptimizationEngine:
    route_name: str = "Madrid → São Paulo"
    competitive: bool = False
    state: EngineState = EngineState.IDLE
    metrics: EngineMetrics = field(default_factory=EngineMetrics)
    last_probe: Optional[ProbeResult] = None
    route_choice: Optional[RouteChoice] = None
    session_started: Optional[float] = None
    _router: RouteSimulator = field(default_factory=RouteSimulator)

    def set_route(self, name: str):
        self.route_name = name
        self.refresh_route(optimized=self.state == EngineState.OPTIMIZING)

    def refresh_route(self, optimized: bool = False):
        real = self.last_probe.combined if self.last_probe else None
        self.route_choice = self._router.choose(self.route_name, real_ping=real, optimized=optimized)

    def probe_once(self) -> ProbeResult:
        self.last_probe = multi_probe()
        return self.last_probe

    def start(self):
        self.state = EngineState.CONNECTING
        self.metrics.ping_before = (
            self.last_probe.combined if self.last_probe and self.last_probe.combined else 180
        )
        self.refresh_route(optimized=True)
        self.state = EngineState.OPTIMIZING
        self.session_started = time.time()

    def stop(self):
        self.state = EngineState.IDLE
        self.session_started = None
        self.refresh_route(optimized=False)

    def tick(self) -> EngineMetrics:
        """Atualiza métricas (1 Hz). Combina probe real + simulação overlay."""
        base = 175
        if self.route_choice:
            base = self.route_choice.overlay_ping_est if self.state == EngineState.OPTIMIZING else self.route_choice.bgp_ping_est

        if self.state == EngineState.OPTIMIZING:
            fator = random.uniform(0.48, 0.60) if self.competitive else random.uniform(0.58, 0.75)
            # ancora no probe real se existir
            if self.last_probe and self.last_probe.combined:
                base = min(base, self.last_probe.combined + 20)
            self.metrics.ping = max(70, int(base * fator + random.uniform(-8, 8)))
            self.metrics.loss = round(random.uniform(0, 0.4), 1)
            self.metrics.jitter = random.randint(1, 8)
        else:
            if self.last_probe and self.last_probe.combined:
                self.metrics.ping = self.last_probe.combined + random.randint(-5, 12)
            else:
                self.metrics.ping = int(base + random.uniform(-15, 20))
            self.metrics.ping = max(70, self.metrics.ping)
            self.metrics.loss = round(random.uniform(0.8, 3.5), 1)
            self.metrics.jitter = random.randint(8, 28)

        self.metrics.quality = self._quality(self.metrics.ping)
        return self.metrics

    @staticmethod
    def _quality(ping: int) -> str:
        if ping < 100:
            return "Excelente"
        if ping < 140:
            return "Muito bom"
        if ping < 180:
            return "Bom"
        if ping < 220:
            return "Médio"
        if ping < 280:
            return "Alto"
        return "Muito alto"

    def session_seconds(self) -> int:
        if not self.session_started:
            return 0
        return int(time.time() - self.session_started)

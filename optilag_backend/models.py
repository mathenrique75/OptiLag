"""
OptiLag — modelos Pydantic v2 (validação + serialização avançadas).

Recursos usados:
  - Enum, Field constraints
  - field_validator mode='before' | 'after'
  - model_validator mode='before' | 'after'
  - computed_field
  - Alias / AliasChoices (JSON snake + camel)
  - model_dump / model_dump_json / model_validate_json
  - Modelos aninhados (nested)
  - ConfigDict: extra, str_strip_whitespace, populate_by_name, ser_json_timedelta
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    AliasChoices,
    field_validator,
    model_validator,
    computed_field,
    field_serializer,
)


# ===========================================================================
# Enums
# ===========================================================================

class EngineActionType(str, Enum):
    start = "start"
    stop = "stop"
    tick = "tick"


class ProbeMethod(str, Enum):
    udp_tcp = "UDP+TCP"
    udp = "UDP"
    tcp = "TCP"
    icmp = "ICMP"


class EngineStateName(str, Enum):
    idle = "idle"
    connecting = "connecting"
    optimizing = "optimizing"
    stopped = "stopped"


# ===========================================================================
# Base com defaults de projeto
# ===========================================================================

class OptiLagModel(BaseModel):
    """Base comum: aceita alias, recusa extras, strip em strings."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,       # permite campo Python OU alias
        use_enum_values=False,       # mantém Enum nos objetos; serializa valor no JSON
        ser_json_timedelta="iso8601",
    )


# ===========================================================================
# Network / Probe (nested)
# ===========================================================================

class ProbeSamples(OptiLagModel):
    """Amostras brutas aninhadas."""
    udp: List[int] = Field(default_factory=list, description="RTTs UDP em ms")
    tcp: List[int] = Field(default_factory=list, description="RTTs TCP em ms")

    @field_validator("udp", "tcp", mode="before")
    @classmethod
    def coerce_list(cls, v: Any) -> list:
        if v is None:
            return []
        if isinstance(v, (int, float)):
            return [int(v)]
        return list(v)

    @field_validator("udp", "tcp", mode="after")
    @classmethod
    def non_negative(cls, v: List[int]) -> List[int]:
        for x in v:
            if x < 0:
                raise ValueError("RTT não pode ser negativo")
        return v


class ProbeOut(OptiLagModel):
    """Resposta GET /probe."""
    udp: Optional[int] = Field(None, ge=0, validation_alias=AliasChoices("udp", "udpMs", "udp_ms"))
    tcp: Optional[int] = Field(None, ge=0, validation_alias=AliasChoices("tcp", "tcpMs", "tcp_ms"))
    icmp: Optional[int] = Field(None, ge=0)
    combined: Optional[int] = Field(None, ge=0, validation_alias=AliasChoices("combined", "ping", "rtt"))
    method: Optional[str] = None
    summary: str = "—"
    samples: ProbeSamples = Field(default_factory=ProbeSamples)
    # compat: ainda expõe listas planas se a API antiga preencher samples_udp
    samples_udp: List[int] = Field(default_factory=list, exclude=True)  # interno
    samples_tcp: List[int] = Field(default_factory=list, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_incoming(cls, data: Any) -> Any:
        """mode='before': ainda é dict/raw — normalizar chaves e aninhar samples."""
        if not isinstance(data, dict):
            return data
        d = dict(data)
        # camelCase → snake
        if "udpMs" in d and "udp" not in d:
            d["udp"] = d.pop("udpMs")
        else:
            d.pop("udpMs", None)
        if "tcpMs" in d and "tcp" not in d:
            d["tcp"] = d.pop("tcpMs")
        else:
            d.pop("tcpMs", None)
        if "ping" in d and "combined" not in d:
            d["combined"] = d.pop("ping")
        else:
            d.pop("ping", None)

        def as_list(v):
            if v is None:
                return []
            if isinstance(v, (int, float)):
                return [int(v)]
            return list(v)

        samples = d.get("samples") or {}
        if not isinstance(samples, dict):
            samples = {}
        if "samples_udp" in d:
            samples.setdefault("udp", as_list(d.pop("samples_udp")))
        if "samples_tcp" in d:
            samples.setdefault("tcp", as_list(d.pop("samples_tcp")))
        if "udp" in samples:
            samples["udp"] = as_list(samples["udp"])
        if "tcp" in samples:
            samples["tcp"] = as_list(samples["tcp"])
        d["samples"] = samples
        # evita validar campos internos legados
        d.pop("samples_udp", None)
        d.pop("samples_tcp", None)
        return d

    @model_validator(mode="after")
    def fill_summary_and_samples(self):
        # migrar listas internas → samples se samples vazio
        if not self.samples.udp and self.samples_udp:
            self.samples.udp = list(self.samples_udp)
        if not self.samples.tcp and self.samples_tcp:
            self.samples.tcp = list(self.samples_tcp)
        if self.summary == "—" and self.combined is not None:
            parts = []
            if self.udp is not None:
                parts.append(f"U{self.udp}")
            if self.tcp is not None:
                parts.append(f"T{self.tcp}")
            extra = (" " + "/".join(parts)) if parts else ""
            self.summary = f"{self.combined} ms{extra}"
        return self

    @computed_field
    @property
    def quality(self) -> str:
        p = self.combined
        if p is None:
            return "—"
        if p < 100:
            return "Excelente"
        if p < 140:
            return "Muito bom"
        if p < 180:
            return "Bom"
        if p < 220:
            return "Médio"
        return "Alto"

    @field_serializer("method")
    def ser_method(self, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


# ===========================================================================
# Engine
# ===========================================================================

class EngineAction(OptiLagModel):
    """POST /engine — validação forte de entrada."""

    @model_validator(mode="before")
    @classmethod
    def lowercase_keys(cls, data: Any) -> Any:
        """Aceita CMD, RouteName, etc. mapeando para aliases conhecidos."""
        if not isinstance(data, dict):
            return data
        key_map = {
            "cmd": "action",
            "command": "action",
            "routename": "route",
            "route_name": "route",
            "comp": "competitive",
            "competitivemode": "competitive",
        }
        out = {}
        for k, v in data.items():
            lk = str(k).strip()
            low = lk.lower()
            if low in key_map:
                out[key_map[low]] = v
            else:
                out[low if low in {"action", "route", "competitive"} else lk] = v
        return out

    action: EngineActionType = Field(
        ...,
        validation_alias=AliasChoices("action", "cmd", "command"),
        description="start | stop | tick",
    )
    route: Optional[str] = Field(
        None,
        min_length=2,
        max_length=80,
        validation_alias=AliasChoices("route", "routeName", "route_name"),
    )
    competitive: Optional[bool] = Field(
        False,
        validation_alias=AliasChoices("competitive", "comp", "competitiveMode"),
    )

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("route", mode="before")
    @classmethod
    def empty_route_to_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("competitive", mode="before")
    @classmethod
    def coerce_bool(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on", "sim"}
        return v

    @model_validator(mode="after")
    def route_recommended_on_start(self):
        # Não bloqueia — só normaliza espaços no nome
        if self.route:
            self.route = " ".join(self.route.split())
        return self


class MetricsOut(OptiLagModel):
    ping: int = Field(0, ge=0)
    loss: float = Field(0.0, ge=0, le=100)
    jitter: int = Field(0, ge=0)
    quality: str = "—"
    ping_before: int = Field(0, ge=0, serialization_alias="pingBefore")

    @field_serializer("loss")
    def ser_loss(self, v: float) -> float:
        return round(float(v), 2)


class EngineOut(OptiLagModel):
    state: str
    route: str
    competitive: bool = False
    metrics: MetricsOut
    session_seconds: int = Field(0, ge=0, serialization_alias="sessionSeconds")
    last_probe: Optional[str] = Field(None, serialization_alias="lastProbe")
    probe: Optional[ProbeOut] = None  # nested opcional


# ===========================================================================
# Routing
# ===========================================================================

class RouteCompareOut(OptiLagModel):
    name: str
    bgp_path: str = Field(serialization_alias="bgpPath")
    overlay_path: str = Field(serialization_alias="overlayPath")
    bgp_as: List[str] = Field(default_factory=list, serialization_alias="bgpAs")
    bgp_ping_est: int = Field(serialization_alias="bgpPingEst")
    overlay_ping_est: int = Field(serialization_alias="overlayPingEst")
    gain_ms: int = Field(serialization_alias="gainMs")
    hops: List[str] = Field(default_factory=list)
    algorithm: str = "dijkstra"

    @computed_field
    @property
    def gain_percent(self) -> float:
        if self.bgp_ping_est <= 0:
            return 0.0
        return round(100.0 * self.gain_ms / self.bgp_ping_est, 1)

    @computed_field
    @property
    def recommendation(self) -> str:
        if self.gain_ms >= 60:
            return "overlay_strongly_preferred"
        if self.gain_ms >= 25:
            return "overlay_preferred"
        return "similar"


class RouteQuery(OptiLagModel):
    optimized: bool = True
    real_ping: Optional[int] = Field(
        None, ge=1, le=2000, validation_alias=AliasChoices("real_ping", "realPing", "ping")
    )


# ===========================================================================
# Persistence / meta
# ===========================================================================

class StatsOut(OptiLagModel):
    probes: int = 0
    sessions: int = 0
    avg_ping: Optional[float] = Field(None, serialization_alias="avgPing")

    @field_serializer("avg_ping")
    def ser_avg(self, v: Optional[float]) -> Optional[float]:
        return round(v, 1) if v is not None else None


class SessionOut(OptiLagModel):
    id: int
    started: float
    ended: Optional[float] = None
    route: str
    game: str = ""
    user: str = ""
    ping_before: int = Field(0, serialization_alias="pingBefore")
    ping_after: int = Field(0, serialization_alias="pingAfter")
    duration_sec: int = Field(0, serialization_alias="durationSec")

    @computed_field
    @property
    def started_iso(self) -> str:
        return datetime.fromtimestamp(self.started, tz=timezone.utc).isoformat()

    @computed_field
    @property
    def improvement_ms(self) -> int:
        return max(0, self.ping_before - self.ping_after)


class HealthOut(OptiLagModel):
    ok: bool = True
    ts: float

    @computed_field
    @property
    def ts_iso(self) -> str:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc).isoformat()


# ===========================================================================
# Helpers
# ===========================================================================

def dump_public(model: BaseModel, *, by_alias: bool = True) -> Dict[str, Any]:
    """Serialização para API/JSON: aliases + sem None."""
    return model.model_dump(mode="json", exclude_none=True, by_alias=by_alias)


def dump_pretty(model: BaseModel, *, by_alias: bool = True) -> str:
    return model.model_dump_json(indent=2, exclude_none=True, by_alias=by_alias)


def parse_engine_action(data: Union[dict, str]) -> EngineAction:
    if isinstance(data, str):
        return EngineAction.model_validate_json(data)
    return EngineAction.model_validate(data)


def probe_from_backend(result: Any) -> ProbeOut:
    """Converte objeto ProbeResult do backend → ProbeOut validado."""
    return ProbeOut.model_validate(
        {
            "udp": getattr(result, "udp", None),
            "tcp": getattr(result, "tcp", None),
            "icmp": getattr(result, "icmp", None),
            "combined": getattr(result, "combined", None),
            "method": getattr(result, "method", None),
            "samples_udp": list(getattr(result, "samples_udp", []) or []),
            "samples_tcp": list(getattr(result, "samples_tcp", []) or []),
        }
    )

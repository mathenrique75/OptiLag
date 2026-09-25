"""Demo completa — validação e serialização avançadas.

  python -m optilag_backend.learn_pydantic
"""
from __future__ import annotations

import json
from pydantic import ValidationError

from optilag_backend.models import (
    EngineAction,
    EngineActionType,
    ProbeOut,
    ProbeSamples,
    RouteCompareOut,
    SessionOut,
    dump_public,
    dump_pretty,
    parse_engine_action,
)


def section(t: str):
    print(f"\n{'='*62}\n{t}\n{'='*62}")


def show_err(e: ValidationError):
    print(json.dumps(e.errors(), indent=2, ensure_ascii=False, default=str))


def main():
    section("1) mode=before — normaliza action e bool")
    a = EngineAction.model_validate(
        {"CMD": "START", "routeName": "  Madrid → São Paulo  ", "comp": "sim"}
    )
    # CMD/routeName/comp são aliases
    print(a)
    print("enum:", a.action, a.action == EngineActionType.start)

    section("2) mode=before — samples de int único → lista")
    p = ProbeOut.model_validate(
        {"ping": 42, "udpMs": 38, "tcpMs": 45, "samples_udp": 40, "method": "udp+tcp"}
    )
    print(dump_pretty(p))
    print("quality:", p.quality)

    section("3) Nested ProbeSamples")
    p2 = ProbeOut(
        combined=50,
        udp=48,
        tcp=52,
        method="UDP+TCP",
        samples=ProbeSamples(udp=[48, 50, 47], tcp=[51, 53]),
    )
    print(dump_public(p2))

    section("4) extra=forbid")
    try:
        EngineAction.model_validate({"action": "start", "admin": True})
    except ValidationError as e:
        show_err(e)

    section("5) Enum inválido")
    try:
        parse_engine_action({"action": "launch"})
    except ValidationError as e:
        show_err(e)

    section("6) Serialização by_alias (camelCase na saída)")
    route = RouteCompareOut(
        name="Madrid → São Paulo",
        bgp_path="PT → ES → BR",
        overlay_path="Portugal → Madrid → São Paulo",
        bgp_as=["AS-PT", "AS-ES"],
        bgp_ping_est=195,
        overlay_ping_est=108,
        gain_ms=87,
        hops=["Portugal", "Madrid", "São Paulo"],
    )
    print(dump_pretty(route, by_alias=True))
    print("recommendation:", route.recommendation)

    section("7) SessionOut computed fields")
    s = SessionOut(
        id=1, started=1_700_000_000.0, ended=1_700_000_120.0,
        route="Madrid → São Paulo", ping_before=190, ping_after=110, duration_sec=120,
    )
    print(dump_pretty(s))
    print("improvement_ms:", s.improvement_ms)

    section("8) model_validate_json")
    print(parse_engine_action('{"command":"tick","competitiveMode":false}'))

    section("9) loss serializer (round)")
    from optilag_backend.models import MetricsOut, EngineOut
    eng = EngineOut(
        state="optimizing",
        route="Madrid → São Paulo",
        metrics=MetricsOut(ping=95, loss=0.3333, jitter=4, quality="Excelente", ping_before=180),
        session_seconds=42,
        probe=p2,
    )
    print(dump_pretty(eng))

    print("\n✓ Demo completa")


if __name__ == "__main__":
    main()

"""Testes unitários — Pydantic models."""
import pytest
from pydantic import ValidationError

from optilag_backend.models import (
    EngineAction,
    EngineActionType,
    ProbeOut,
    RouteCompareOut,
    parse_engine_action,
)


def test_engine_action_valid():
    a = EngineAction.model_validate({"action": "start", "route": "Madrid → São Paulo"})
    assert a.action == EngineActionType.start
    assert "Madrid" in a.route


def test_engine_action_aliases():
    a = parse_engine_action({"cmd": "STOP", "comp": "sim"})
    assert a.action == EngineActionType.stop
    assert a.competitive is True


def test_engine_action_invalid():
    with pytest.raises(ValidationError):
        EngineAction.model_validate({"action": "explode"})


def test_engine_action_extra_forbidden():
    with pytest.raises(ValidationError):
        EngineAction.model_validate({"action": "start", "hacker": True})


def test_probe_out_quality():
    p = ProbeOut(combined=42, udp=38, tcp=45, method="UDP+TCP")
    assert p.quality == "Excelente"
    assert "42" in p.summary


def test_route_gain_percent():
    r = RouteCompareOut(
        name="Test",
        bgp_path="A → B",
        overlay_path="A → X → B",
        bgp_as=[],
        bgp_ping_est=200,
        overlay_ping_est=100,
        gain_ms=100,
        hops=["A", "B"],
    )
    assert r.gain_percent == 50.0
    assert r.recommendation == "overlay_strongly_preferred"

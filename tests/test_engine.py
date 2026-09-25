"""Testes unitários — motor de sessão."""
from optilag_backend.core.engine import OptimizationEngine, EngineState
from optilag_backend.network.probes import ProbeResult


def test_engine_start_stop():
    eng = OptimizationEngine(route_name="Madrid → São Paulo")
    eng.last_probe = ProbeResult(combined=180, method="UDP+TCP")
    assert eng.state == EngineState.IDLE

    eng.start()
    assert eng.state == EngineState.OPTIMIZING
    assert eng.session_started is not None

    m = eng.tick()
    assert m.ping >= 70
    assert m.quality

    eng.stop()
    assert eng.state == EngineState.IDLE


def test_quality_bands():
    assert OptimizationEngine._quality(80) == "Excelente"
    assert OptimizationEngine._quality(150) == "Bom"
    assert OptimizationEngine._quality(300) == "Muito alto"

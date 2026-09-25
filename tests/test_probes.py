"""Testes unitários — probes (funções puras / estrutura)."""
from optilag_backend.network.probes import (
    _build_dns_query,
    _median,
    ProbeResult,
    multi_probe,
)


def test_build_dns_query_not_empty():
    q = _build_dns_query("www.google.com.br")
    assert isinstance(q, bytes)
    assert len(q) > 20


def test_median():
    assert _median([]) is None
    assert _median([10]) == 10
    assert _median([10, 20, 30]) == 20


def test_probe_result_summary():
    r = ProbeResult(udp=40, tcp=50, combined=45, method="UDP+TCP")
    s = r.summary()
    assert "45" in s
    assert "U40" in s


def test_multi_probe_returns_result():
    """Integração leve: precisa de rede. Se falhar tudo, combined pode ser None."""
    r = multi_probe()
    assert isinstance(r, ProbeResult)
    # em CI com rede, costuma haver combined; não exigimos valor fixo
    if r.combined is not None:
        assert r.combined >= 1
        assert r.method in ("UDP+TCP", "UDP", "TCP", "ICMP")

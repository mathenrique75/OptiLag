"""Probes com mocks — sem rede real."""
from unittest.mock import MagicMock, patch

from optilag_backend.network.probes import medir_udp_dns, medir_tcp_rtt, multi_probe, ProbeResult


def test_medir_udp_dns_success():
    fake_sock = MagicMock()
    fake_sock.recvfrom.return_value = (b"\x00" * 20, ("1.1.1.1", 53))

    with patch("socket.socket", return_value=fake_sock):
        with patch("time.perf_counter", side_effect=[100.0, 100.042]):
            rtt = medir_udp_dns("1.1.1.1", 53)

    assert rtt == 42
    fake_sock.sendto.assert_called_once()
    fake_sock.close.assert_called()


def test_medir_udp_dns_timeout():
    fake_sock = MagicMock()
    fake_sock.sendto.side_effect = TimeoutError("timeout")

    with patch("socket.socket", return_value=fake_sock):
        rtt = medir_udp_dns("1.1.1.1", 53)

    assert rtt is None


def test_medir_tcp_rtt_success():
    fake_sock = MagicMock()
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("1.1.1.1", 443))]):
        with patch("socket.socket", return_value=fake_sock):
            with patch("time.perf_counter", side_effect=[50.0, 50.03]):
                rtt = medir_tcp_rtt("1.1.1.1", 443)

    assert rtt == 30
    fake_sock.connect.assert_called_once()


def test_multi_probe_uses_udp_and_tcp():
    with patch("optilag_backend.network.probes.medir_udp_dns", return_value=40):
        with patch("optilag_backend.network.probes.medir_tcp_rtt", return_value=50):
            with patch("optilag_backend.network.probes.medir_icmp", return_value=None):
                r = multi_probe()

    assert isinstance(r, ProbeResult)
    assert r.udp == 40
    assert r.tcp == 50
    assert r.combined in (40, 50)
    assert r.method == "UDP+TCP"

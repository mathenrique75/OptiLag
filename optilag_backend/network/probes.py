"""Sondas de latência: UDP (DNS), TCP (handshake), ICMP (fallback)."""
from __future__ import annotations

import random
import socket
import subprocess
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


UDP_DNS_TARGETS: List[Tuple[str, int]] = [
    ("1.1.1.1", 53),
    ("8.8.8.8", 53),
    ("8.8.4.4", 53),
    ("208.67.222.222", 53),
]

TCP_TARGETS: List[Tuple[str, int]] = [
    ("1.1.1.1", 443),
    ("8.8.8.8", 443),
    ("www.google.com.br", 443),
]

ICMP_HOSTS = ["1.1.1.1", "8.8.8.8", "www.google.com.br"]


@dataclass
class ProbeResult:
    udp: Optional[int] = None
    tcp: Optional[int] = None
    icmp: Optional[int] = None
    combined: Optional[int] = None
    method: Optional[str] = None
    samples_udp: List[int] = field(default_factory=list)
    samples_tcp: List[int] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> str:
        if self.combined is None:
            return "—"
        parts = []
        if self.udp is not None:
            parts.append(f"U{self.udp}")
        if self.tcp is not None:
            parts.append(f"T{self.tcp}")
        if self.icmp is not None and self.method == "ICMP":
            parts.append(f"I{self.icmp}")
        extra = (" " + "/".join(parts)) if parts else ""
        return f"{self.combined} ms{extra}"


def _build_dns_query(domain: str = "www.google.com.br") -> bytes:
    txid = random.randint(0, 65535)
    header = txid.to_bytes(2, "big") + bytes([0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    q = b""
    for label in domain.split("."):
        q += bytes([len(label)]) + label.encode("ascii")
    q += bytes([0x00, 0x00, 0x01, 0x00, 0x01])
    return header + q


def medir_udp_dns(host: str, port: int = 53, timeout: float = 1.5) -> Optional[int]:
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        t0 = time.perf_counter()
        sock.sendto(_build_dns_query(), (host, port))
        data, _ = sock.recvfrom(512)
        t1 = time.perf_counter()
        if data and len(data) >= 12:
            return max(1, int((t1 - t0) * 1000))
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return None


def medir_tcp_rtt(host: str, port: int = 443, timeout: float = 1.5) -> Optional[int]:
    sock = None
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return None
        addr = infos[0][4]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        t0 = time.perf_counter()
        sock.connect(addr)
        t1 = time.perf_counter()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        return max(1, int((t1 - t0) * 1000))
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def medir_icmp(host: str, timeout_ms: int = 1500) -> Optional[int]:
    try:
        import sys
        if sys.platform.startswith("win"):
            r = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout_ms), host],
                capture_output=True, text=True, timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            m = re.search(r"(?:tempo|time)[=<>](\d+)\s*ms", r.stdout, re.I)
        else:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), host],
                capture_output=True, text=True, timeout=3,
            )
            m = re.search(r"time[=<>]([\d.]+)\s*ms", r.stdout, re.I)
        if m:
            return int(float(m.group(1)))
    except Exception:
        return None
    return None


def _median(values: List[int]) -> Optional[int]:
    if not values:
        return None
    s = sorted(values)
    return s[len(s) // 2]


def multi_probe(max_udp: int = 3, max_tcp: int = 2) -> ProbeResult:
    """Executa sondas UDP + TCP (+ ICMP se necessário)."""
    result = ProbeResult()

    for host, port in UDP_DNS_TARGETS:
        rtt = medir_udp_dns(host, port)
        if rtt is not None:
            result.samples_udp.append(rtt)
        if len(result.samples_udp) >= max_udp:
            break
    result.udp = _median(result.samples_udp)

    for host, port in TCP_TARGETS:
        rtt = medir_tcp_rtt(host, port)
        if rtt is not None:
            result.samples_tcp.append(rtt)
        if len(result.samples_tcp) >= max_tcp:
            break
    result.tcp = _median(result.samples_tcp)

    samples = [x for x in (result.udp, result.tcp) if x is not None]
    if samples:
        result.combined = _median(samples)
        if result.udp is not None and result.tcp is not None:
            result.method = "UDP+TCP"
        elif result.udp is not None:
            result.method = "UDP"
        else:
            result.method = "TCP"
        return result

    for host in ICMP_HOSTS:
        rtt = medir_icmp(host)
        if rtt is not None:
            result.icmp = rtt
            result.combined = rtt
            result.method = "ICMP"
            return result

    return result

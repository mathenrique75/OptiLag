"""Simulador BGP (ISP) vs Overlay — educativo, não altera rotas reais."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .graph import RouteGraph, RouteNode, dijkstra


@dataclass
class RouteChoice:
    name: str
    bgp_path: str
    overlay_path: str
    bgp_as: List[str]
    bgp_ping_est: int
    overlay_ping_est: int
    overlay_hops: List[str]
    gain_ms: int
    algorithm: str = "dijkstra"


def build_default_graph() -> RouteGraph:
    g = RouteGraph()
    for nid, label, region in [
        ("pt", "Portugal", "EU"),
        ("mad", "Madrid", "EU"),
        ("lon", "Londres", "EU"),
        ("fra", "Frankfurt", "EU"),
        ("mia", "Miami", "US"),
        ("sp", "São Paulo", "BR"),
    ]:
        g.add_node(RouteNode(nid, label, region))

    # custos simétricos aproximados (ms)
    links = [
        ("pt", "mad", 15),
        ("pt", "lon", 35),
        ("pt", "fra", 40),
        ("mad", "sp", 160),
        ("lon", "sp", 175),
        ("fra", "sp", 180),
        ("pt", "mia", 90),
        ("mia", "sp", 120),
        ("pt", "sp", 195),  # direto "ruim"
        ("mad", "lon", 25),
        ("mad", "fra", 30),
        ("lon", "fra", 20),
    ]
    for a, b, c in links:
        g.add_edge(a, b, c)
    return g


# Metadados estilo BGP por perfil de rota da UI
ROUTE_PROFILES: Dict[str, dict] = {
    "São Paulo (Direto)": {
        "via": None,
        "bgp_path": "PT → EU-core → BR",
        "bgp_as": ["AS-PT-ISP", "AS1299 Arelion", "AS10429 BR", "AS-GAME"],
        "bgp_base": 210,
    },
    "Madrid → São Paulo": {
        "via": "mad",
        "bgp_path": "PT → ES → BR",
        "bgp_as": ["AS-PT-ISP", "AS3352 ES", "AS10429 BR", "AS-GAME"],
        "bgp_base": 195,
    },
    "Londres → São Paulo": {
        "via": "lon",
        "bgp_path": "PT → UK → backbone → BR",
        "bgp_as": ["AS-PT-ISP", "AS174 Cogent", "AS3356 Level3", "AS-GAME"],
        "bgp_base": 205,
    },
    "Frankfurt → São Paulo": {
        "via": "fra",
        "bgp_path": "PT → DE → EU-IX → BR",
        "bgp_as": ["AS-PT-ISP", "AS3320 DT", "AS1299", "AS-GAME"],
        "bgp_base": 200,
    },
    "Miami → São Paulo": {
        "via": "mia",
        "bgp_path": "PT → US-East → Miami → BR",
        "bgp_as": ["AS-PT-ISP", "AS3356 Level3", "AS-MIA", "AS-GAME"],
        "bgp_base": 230,
    },
}


class RouteSimulator:
    def __init__(self, graph: Optional[RouteGraph] = None):
        self.graph = graph or build_default_graph()

    def choose(self, profile_name: str, real_ping: Optional[int] = None, optimized: bool = False) -> RouteChoice:
        profile = ROUTE_PROFILES.get(profile_name, ROUTE_PROFILES["Madrid → São Paulo"])
        via = profile.get("via")

        if via:
            path1, c1 = dijkstra(self.graph, "pt", via)
            path2, c2 = dijkstra(self.graph, via, "sp")
            if path1 and path2 and path2[0] == via:
                full = path1 + path2[1:]
                cost = c1 + c2
            else:
                full, cost = dijkstra(self.graph, "pt", "sp")
        else:
            # Rota "direta": usa só a aresta PT—SP (sem nós intermédios)
            full = ["pt", "sp"]
            cost = self.graph.edges.get("pt", {}).get("sp", 195)

        labels = [self.graph.nodes[n].label for n in full if n in self.graph.nodes]
        overlay_path = " → ".join(labels) if labels else profile_name

        bgp_est = profile["bgp_base"]
        if real_ping and real_ping > 50:
            bgp_est = int(real_ping * 1.05 + 10)

        overlay_est = int(cost) if cost != float("inf") else profile["bgp_base"] - 20
        if optimized:
            overlay_est = int(overlay_est * 0.62)
        else:
            # sem otimizar, overlay "desligado" ≈ BGP
            overlay_est = bgp_est

        gain = max(0, bgp_est - overlay_est)
        return RouteChoice(
            name=profile_name,
            bgp_path=profile["bgp_path"],
            overlay_path=f"PT → {overlay_path}" if not overlay_path.startswith("Portugal") else overlay_path,
            bgp_as=list(profile["bgp_as"]),
            bgp_ping_est=bgp_est,
            overlay_ping_est=overlay_est,
            overlay_hops=labels,
            gain_ms=gain,
            algorithm="dijkstra",
        )

    def best_overlay(self) -> RouteChoice:
        """Escolhe o perfil com menor custo overlay (otimizado)."""
        best = None
        for name in ROUTE_PROFILES:
            choice = self.choose(name, optimized=True)
            if best is None or choice.overlay_ping_est < best.overlay_ping_est:
                best = choice
        return best

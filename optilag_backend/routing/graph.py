"""Grafo de nós overlay + Dijkstra para escolha de caminho."""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class RouteNode:
    id: str
    label: str
    region: str


@dataclass
class RouteGraph:
    nodes: Dict[str, RouteNode] = field(default_factory=dict)
    # edges[a][b] = cost (latency ms)
    edges: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def add_node(self, node: RouteNode):
        self.nodes[node.id] = node
        self.edges.setdefault(node.id, {})

    def add_edge(self, a: str, b: str, cost: float, bidirectional: bool = True):
        self.edges.setdefault(a, {})[b] = cost
        if bidirectional:
            self.edges.setdefault(b, {})[a] = cost

    def neighbors(self, node_id: str) -> List[Tuple[str, float]]:
        return list(self.edges.get(node_id, {}).items())


def dijkstra(graph: RouteGraph, source: str, target: str) -> Tuple[List[str], float]:
    """Devolve (caminho de ids, custo total). Caminho vazio se impossível."""
    if source not in graph.nodes or target not in graph.nodes:
        return [], float("inf")

    dist = {n: float("inf") for n in graph.nodes}
    prev = {n: None for n in graph.nodes}
    dist[source] = 0.0
    pq = [(0.0, source)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == target:
            break
        for v, w in graph.neighbors(u):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if dist[target] == float("inf"):
        return [], float("inf")

    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path, dist[target]

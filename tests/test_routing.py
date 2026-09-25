"""Testes unitários — grafo e Dijkstra."""
from optilag_backend.routing.graph import RouteGraph, RouteNode, dijkstra
from optilag_backend.routing.simulator import RouteSimulator, build_default_graph


def test_dijkstra_simple_path():
    g = RouteGraph()
    g.add_node(RouteNode("a", "A", "EU"))
    g.add_node(RouteNode("b", "B", "EU"))
    g.add_node(RouteNode("c", "C", "BR"))
    g.add_edge("a", "b", 10)
    g.add_edge("b", "c", 20)
    g.add_edge("a", "c", 100)  # caminho direto pior

    path, cost = dijkstra(g, "a", "c")
    assert path == ["a", "b", "c"]
    assert cost == 30


def test_dijkstra_unreachable():
    g = RouteGraph()
    g.add_node(RouteNode("a", "A", "EU"))
    g.add_node(RouteNode("z", "Z", "BR"))
    path, cost = dijkstra(g, "a", "z")
    assert path == []
    assert cost == float("inf")


def test_default_graph_pt_to_sp():
    g = build_default_graph()
    path, cost = dijkstra(g, "pt", "sp")
    assert "pt" in path and "sp" in path
    assert cost < 200


def test_simulator_madrid_optimized():
    sim = RouteSimulator()
    choice = sim.choose("Madrid → São Paulo", optimized=True)
    assert choice.overlay_ping_est < choice.bgp_ping_est
    assert choice.gain_ms > 0
    assert "Madrid" in choice.overlay_hops or "Portugal" in choice.overlay_hops


def test_best_overlay_returns_choice():
    best = RouteSimulator().best_overlay()
    assert best.name
    assert best.overlay_ping_est > 0

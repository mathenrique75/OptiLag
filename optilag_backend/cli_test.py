"""Teste rápido do backend sem UI: python -m optilag_backend.cli_test"""
from __future__ import annotations

import sys
import os

# permite correr a partir de artifacts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optilag_backend.network.probes import multi_probe
from optilag_backend.routing.simulator import RouteSimulator
from optilag_backend.core.engine import OptimizationEngine


def main():
    print("=== OptiLag Backend Test ===\n")

    print("1) Multi-probe (UDP+TCP)...")
    probe = multi_probe()
    print(f"   {probe.summary()}  method={probe.method}")
    print(f"   udp={probe.udp} tcp={probe.tcp} icmp={probe.icmp}")
    print(f"   samples_udp={probe.samples_udp} samples_tcp={probe.samples_tcp}\n")

    print("2) Dijkstra overlay routes...")
    sim = RouteSimulator()
    for name in ["Madrid → São Paulo", "Miami → São Paulo", "São Paulo (Direto)"]:
        c = sim.choose(name, real_ping=probe.combined, optimized=True)
        print(f"   {name}")
        print(f"      BGP:     {c.bgp_path}  ~{c.bgp_ping_est} ms")
        print(f"      Overlay: {c.overlay_path}  ~{c.overlay_ping_est} ms  (-{c.gain_ms} ms)")
        print(f"      hops={c.overlay_hops}  algo={c.algorithm}")

    best = sim.best_overlay()
    print(f"\n   Best overlay: {best.name} ~{best.overlay_ping_est} ms\n")

    print("3) Engine session tick...")
    eng = OptimizationEngine(route_name="Madrid → São Paulo")
    eng.last_probe = probe
    eng.start()
    for i in range(3):
        m = eng.tick()
        print(f"   tick{i+1}: ping={m.ping} loss={m.loss}% jitter={m.jitter} quality={m.quality}")
    eng.stop()
    
    print("4) Persistence...")
    from optilag_backend.persistence import Persistence
    db = Persistence()
    db.save_probe(probe)
    print("   stats:", db.stats())
    print("   recent probes:", len(db.recent_probes(5)))

    print("\nOK")



if __name__ == "__main__":
    main()

"""Testes — SQLite persistence (Windows-safe: fecha conexões + ignore_cleanup_errors)."""
import os
import tempfile

from optilag_backend.persistence import Persistence
from optilag_backend.network.probes import ProbeResult


def _tmpdir():
    # Python 3.10+: ignore_cleanup_errors evita WinError 32 se o OS atrasar o unlock
    try:
        return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    except TypeError:
        return tempfile.TemporaryDirectory()


def test_save_and_list_probes():
    with _tmpdir() as tmp:
        db = Persistence(os.path.join(tmp, "t.db"))
        p = ProbeResult(udp=40, tcp=50, combined=45, method="UDP+TCP")
        db.save_probe(p)
        rows = db.recent_probes(10)
        assert len(rows) >= 1
        assert rows[0]["combined"] == 45
        assert rows[0]["method"] == "UDP+TCP"


def test_save_session_and_stats():
    with _tmpdir() as tmp:
        db = Persistence(os.path.join(tmp, "t.db"))
        db.save_probe(ProbeResult(combined=100, method="UDP"))
        db.save_session(
            started=1000.0,
            ended=1120.0,
            route="Madrid → São Paulo",
            game="PUBG: Battlegrounds",
            user="admin",
            ping_before=180,
            ping_after=110,
        )
        sessions = db.recent_sessions(5)
        assert len(sessions) == 1
        assert sessions[0]["duration_sec"] == 120
        assert sessions[0]["route"] == "Madrid → São Paulo"

        st = db.stats()
        assert st["probes"] >= 1
        assert st["sessions"] >= 1
        assert st["avg_ping"] is not None


def test_export_json():
    with _tmpdir() as tmp:
        db = Persistence(os.path.join(tmp, "t.db"))
        db.save_probe(ProbeResult(combined=80, method="TCP"))
        out = os.path.join(tmp, "export.json")
        path = db.export_json(out)
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 10

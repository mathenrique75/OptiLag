"""Configuração central do backend (env + defaults)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Definições imutáveis carregadas uma vez."""

    app_name: str = "OptiLag"
    version: str = "0.4.0"
    api_host: str = "127.0.0.1"  # nunca 0.0.0.0 por defeito
    api_port: int = 8765
    debug: bool = False

    # SQLite
    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    db_name: str = "optilag_data.db"

    # Probes / sampler
    sampler_interval_sec: float = 5.0
    sampler_history: int = 120
    probe_timeout_sec: float = 2.0

    # CORS — só localhost por defeito (mais profissional que *)
    cors_origins: tuple = ("http://127.0.0.1:8765", "http://localhost:8765", "null")

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @classmethod
    def from_env(cls) -> "Settings":
        origins = _env("OPTILAG_CORS_ORIGINS", "")
        cors = tuple(o.strip() for o in origins.split(",") if o.strip()) if origins else cls.cors_origins
        data = _env("OPTILAG_DATA_DIR", "")
        data_dir = Path(data) if data else Path(__file__).resolve().parent
        return cls(
            app_name=_env("OPTILAG_APP_NAME", "OptiLag"),
            version=_env("OPTILAG_VERSION", "0.4.0"),
            api_host=_env("OPTILAG_HOST", "127.0.0.1"),
            api_port=_env_int("OPTILAG_PORT", 8765),
            debug=_env_bool("OPTILAG_DEBUG", False),
            data_dir=data_dir,
            db_name=_env("OPTILAG_DB_NAME", "optilag_data.db"),
            sampler_interval_sec=float(_env("OPTILAG_SAMPLER_INTERVAL", "5.0")),
            sampler_history=_env_int("OPTILAG_SAMPLER_HISTORY", 120),
            probe_timeout_sec=float(_env("OPTILAG_PROBE_TIMEOUT", "2.0")),
            cors_origins=cors if cors else ("http://127.0.0.1:8765",),
            log_level=_env("OPTILAG_LOG_LEVEL", "INFO").upper(),
            log_json=_env_bool("OPTILAG_LOG_JSON", False),
        )


# Singleton de processo
settings = Settings.from_env()

"""OptiLag backend."""
try:
    from optilag_backend.config import settings
    __version__ = settings.version
except Exception:
    __version__ = "0.4.0"

__all__ = ["__version__"]

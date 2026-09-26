"""Exceções de domínio do OptiLag backend."""
from __future__ import annotations


class OptiLagError(Exception):
    """Base."""

    def __init__(self, message: str, code: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ProbeError(OptiLagError):
    def __init__(self, message: str = "Falha no probe de rede") -> None:
        super().__init__(message, code="probe_error")


class RouteNotFoundError(OptiLagError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Rota desconhecida: {name}", code="route_not_found")
        self.route = name


class EngineStateError(OptiLagError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="engine_state")


class PersistenceError(OptiLagError):
    def __init__(self, message: str = "Erro de persistência") -> None:
        super().__init__(message, code="persistence_error")


class TunnelError(OptiLagError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="tunnel_error")

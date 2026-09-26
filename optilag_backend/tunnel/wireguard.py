"""
Controlo local do WireGuard (Windows / Linux).

Isto NÃO cria a rede de relays do ExitLag — ativa um tunnel WireGuard
já configurado (ficheiro .conf). O utilizador precisa de:
  1) VPS com WireGuard
  2) WireGuard instalado no PC
  3) Ficheiro .conf do cliente em conf/wg-optilag.conf
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TunnelStatus(str, Enum):
    unknown = "unknown"
    not_installed = "not_installed"
    inactive = "inactive"
    active = "active"
    error = "error"


@dataclass
class TunnelInfo:
    status: TunnelStatus
    name: str = "wg-optilag"
    detail: str = ""
    interface: Optional[str] = None


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        kwargs = dict(capture_output=True, text=True, timeout=timeout)
        if _is_windows():
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(cmd, **kwargs)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "comando nao encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


class WireGuardTunnel:
    """
    Gere um tunnel a partir de um ficheiro .conf.

    Windows: usa `wireguard.exe` (serviço de tunnel).
    Linux: usa `wg-quick`.
    """

    def __init__(self, conf_path: Optional[str] = None, name: str = "wg-optilag"):
        base = Path(__file__).resolve().parents[2]  # pasta do projeto
        default_conf = base / "conf" / "wg-optilag.conf"
        self.conf_path = Path(conf_path) if conf_path else default_conf
        self.name = name

    def wireguard_installed(self) -> bool:
        if _is_windows():
            # wireguard.exe costuma estar em Program Files
            candidates = [
                shutil.which("wireguard"),
                r"C:\Program Files\WireGuard\wireguard.exe",
                r"C:\Program Files (x86)\WireGuard\wireguard.exe",
            ]
            return any(p and Path(p).is_file() for p in candidates)
        return shutil.which("wg-quick") is not None or shutil.which("wg") is not None

    def _wg_exe(self) -> Optional[str]:
        if not _is_windows():
            return shutil.which("wg-quick")
        for p in (
            shutil.which("wireguard"),
            r"C:\Program Files\WireGuard\wireguard.exe",
            r"C:\Program Files (x86)\WireGuard\wireguard.exe",
        ):
            if p and Path(p).is_file():
                return p
        return None

    def conf_exists(self) -> bool:
        return self.conf_path.is_file()

    def status(self) -> TunnelInfo:
        if not self.wireguard_installed():
            return TunnelInfo(TunnelStatus.not_installed, self.name, "Instala WireGuard: https://www.wireguard.com/install/")

        if not self.conf_exists():
            return TunnelInfo(
                TunnelStatus.inactive,
                self.name,
                f"Falta config: {self.conf_path} (ver conf/README.md)",
            )

        if _is_windows():
            # Lista tunnels / interfaces
            code, out, err = _run(["wg", "show"], timeout=10)
            if code == 127:
                # wg pode nao estar no PATH; tenta powershell Get-NetAdapter
                code2, out2, _ = _run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-NetAdapter | Where-Object {$_.InterfaceDescription -match 'WireGuard'} | Select-Object -ExpandProperty Name"],
                    timeout=15,
                )
                if out2.strip():
                    return TunnelInfo(TunnelStatus.active, self.name, "Interface WireGuard ativa", out2.splitlines()[0].strip())
                return TunnelInfo(TunnelStatus.inactive, self.name, "Tunnel inativo")
            if code == 0 and out.strip():
                iface = out.splitlines()[0].split(":")[0].strip() if ":" in out.splitlines()[0] else "wg"
                return TunnelInfo(TunnelStatus.active, self.name, "Tunnel ativo", iface)
            return TunnelInfo(TunnelStatus.inactive, self.name, "Tunnel inativo")

        code, out, err = _run(["wg", "show"], timeout=10)
        if code == 0 and out.strip():
            return TunnelInfo(TunnelStatus.active, self.name, "Tunnel ativo")
        return TunnelInfo(TunnelStatus.inactive, self.name, "Tunnel inativo")

    def up(self) -> TunnelInfo:
        if not self.wireguard_installed():
            return self.status()
        if not self.conf_exists():
            return TunnelInfo(TunnelStatus.error, self.name, f"Config em falta: {self.conf_path}")

        if _is_windows():
            exe = self._wg_exe()
            if not exe:
                return TunnelInfo(TunnelStatus.not_installed, self.name, "wireguard.exe nao encontrado")
            # Instala/ativa o tunnel como servico (requer admin)
            code, out, err = _run([exe, "/installtunnelservice", str(self.conf_path)], timeout=60)
            if code != 0:
                # fallback: abrir UI
                _run([exe, str(self.conf_path)], timeout=10)
                return TunnelInfo(
                    TunnelStatus.error,
                    self.name,
                    f"Falha ao ativar (corre como Administrador?). {err or out}",
                )
            time.sleep(1.5)
            return self.status()

        code, out, err = _run(["wg-quick", "up", str(self.conf_path)], timeout=60)
        if code != 0:
            return TunnelInfo(TunnelStatus.error, self.name, err or out or "wg-quick up falhou")
        return self.status()

    def down(self) -> TunnelInfo:
        if _is_windows():
            exe = self._wg_exe()
            if not exe:
                return TunnelInfo(TunnelStatus.not_installed, self.name, "wireguard.exe nao encontrado")
            # Nome do servico = nome do ficheiro conf sem extensao
            svc = self.conf_path.stem
            code, out, err = _run([exe, "/uninstalltunnelservice", svc], timeout=60)
            if code != 0:
                return TunnelInfo(TunnelStatus.error, self.name, err or out or "falha ao desativar")
            time.sleep(1)
            return self.status()

        code, out, err = _run(["wg-quick", "down", str(self.conf_path)], timeout=60)
        if code != 0:
            return TunnelInfo(TunnelStatus.error, self.name, err or out)
        return self.status()

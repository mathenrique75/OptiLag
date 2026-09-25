"""Controlo local WireGuard (Windows/Linux)."""
from __future__ import annotations
import platform, shutil, subprocess, time
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

def _run(cmd, timeout=30):
    try:
        kwargs = dict(capture_output=True, text=True, timeout=timeout)
        if _is_windows():
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(cmd, **kwargs)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "comando nao encontrado"
    except Exception as e:
        return 1, "", str(e)

class WireGuardTunnel:
    def __init__(self, conf_path=None, name="wg-optilag"):
        base = Path(__file__).resolve().parents[2]
        self.conf_path = Path(conf_path) if conf_path else base / "conf" / "wg-optilag.conf"
        self.name = name

    def wireguard_installed(self) -> bool:
        if _is_windows():
            for p in (shutil.which("wireguard"),
                      r"C:\Program Files\WireGuard\wireguard.exe",
                      r"C:\Program Files (x86)\WireGuard\wireguard.exe"):
                if p and Path(p).is_file():
                    return True
            return False
        return shutil.which("wg-quick") is not None or shutil.which("wg") is not None

    def _wg_exe(self):
        if not _is_windows():
            return shutil.which("wg-quick")
        for p in (shutil.which("wireguard"),
                  r"C:\Program Files\WireGuard\wireguard.exe",
                  r"C:\Program Files (x86)\WireGuard\wireguard.exe"):
            if p and Path(p).is_file():
                return p
        return None

    def conf_exists(self) -> bool:
        return self.conf_path.is_file()

    def status(self) -> TunnelInfo:
        if not self.wireguard_installed():
            return TunnelInfo(TunnelStatus.not_installed, self.name,
                              "Instala WireGuard: https://www.wireguard.com/install/")
        if not self.conf_exists():
            return TunnelInfo(TunnelStatus.inactive, self.name,
                              f"Falta config: {self.conf_path}")
        code, out, err = _run(["wg", "show"], timeout=10)
        if code == 0 and out.strip():
            return TunnelInfo(TunnelStatus.active, self.name, "Tunnel ativo")
        if _is_windows():
            code2, out2, _ = _run([
                "powershell", "-NoProfile", "-Command",
                "Get-NetAdapter | Where-Object {$_.InterfaceDescription -match 'WireGuard'} | Select-Object -ExpandProperty Name"
            ], timeout=15)
            if out2.strip():
                return TunnelInfo(TunnelStatus.active, self.name, "Interface WireGuard ativa", out2.splitlines()[0].strip())
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
            code, out, err = _run([exe, "/installtunnelservice", str(self.conf_path)], timeout=60)
            if code != 0:
                return TunnelInfo(TunnelStatus.error, self.name,
                                  f"Falha (corre como Admin?). {err or out}")
            time.sleep(1.5)
            return self.status()
        code, out, err = _run(["wg-quick", "up", str(self.conf_path)], timeout=60)
        if code != 0:
            return TunnelInfo(TunnelStatus.error, self.name, err or out)
        return self.status()

    def down(self) -> TunnelInfo:
        if _is_windows():
            exe = self._wg_exe()
            if not exe:
                return TunnelInfo(TunnelStatus.not_installed, self.name, "wireguard.exe nao encontrado")
            code, out, err = _run([exe, "/uninstalltunnelservice", self.conf_path.stem], timeout=60)
            if code != 0:
                return TunnelInfo(TunnelStatus.error, self.name, err or out)
            time.sleep(1)
            return self.status()
        code, out, err = _run(["wg-quick", "down", str(self.conf_path)], timeout=60)
        if code != 0:
            return TunnelInfo(TunnelStatus.error, self.name, err or out)
        return self.status()

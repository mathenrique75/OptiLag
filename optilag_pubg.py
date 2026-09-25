import sys as _sys
from pathlib import Path as _Path
# Garante que optilag_backend é importável (pasta do script)
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import customtkinter as ctk
import threading
import time
import random
import sys
import os
import json
import urllib.request
import subprocess
import re
import hashlib
import secrets
import string
from datetime import datetime

# ==================== IMPORTS OPCIONAIS ====================
# --- Backend OptiLag ---
try:
    from optilag_backend.bridge import (
        probe_now, measure_combined, route_compare, get_sampler,
        start_optimization, stop_optimization, tick as engine_tick,
        db as backend_db, engine as backend_engine, router as backend_router,
    )
    HAS_BACKEND = True
except Exception as _be:
    HAS_BACKEND = False
    print(f"[backend] offline: {_be}")

try:
    import winreg
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    from win10toast import ToastNotifier
    toaster = ToastNotifier()
    HAS_TOAST = True
except Exception:
    HAS_TOAST = False

try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_GRAPH = True
except ImportError:
    HAS_GRAPH = False

# ==================== CONSTANTES ====================
APP_NAME = "OptiLag"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "optilag_config.json")
HISTORY_FILE = os.path.join(BASE_DIR, "optilag_history.json")
AUTH_FILE = os.path.join(BASE_DIR, "optilag_auth.json")

ICON_DIR = os.path.join(BASE_DIR, "icons")

JOGOS = {
    "PUBG: Battlegrounds": {"processos": ["TslGame.exe", "PUBG.exe", "ShooterGame.exe"], "extra": 0, "icon": "pubg", "cor": "#5dce7a", "cor_hover": "#3daa5a"},
    "Valorant": {"processos": ["VALORANT-Win64-Shipping.exe", "VALORANT.exe"], "extra": -5, "icon": "valorant", "cor": "#ff4655", "cor_hover": "#d6303f"},
    "Counter-Strike 2": {"processos": ["cs2.exe"], "extra": -8, "icon": "cs2", "cor": "#decc4a", "cor_hover": "#b8a830"},
    "Fortnite": {"processos": ["FortniteClient-Win64-Shipping.exe"], "extra": 5, "icon": "fortnite", "cor": "#7b5cff", "cor_hover": "#5a3fd6"},
    "League of Legends": {"processos": ["League of Legends.exe", "LeagueClient.exe"], "extra": -10, "icon": "lol", "cor": "#4aa3ff", "cor_hover": "#2a7fd6"},
    "Apex Legends": {"processos": ["r5apex.exe"], "extra": 0, "icon": "apex", "cor": "#ff5a3c", "cor_hover": "#d64028"},
    "Call of Duty: Warzone": {"processos": ["cod.exe", "ModernWarfare.exe"], "extra": 8, "icon": "warzone", "cor": "#6dce50", "cor_hover": "#4aa830"},
    "Roblox": {"processos": ["RobloxPlayerBeta.exe"], "extra": -15, "icon": "roblox", "cor": "#e2231a", "cor_hover": "#b01a14"},
}

APP_VERSION = "2.1"


def carregar_icone(nome: str, size: int = 32):
    """Carrega ícone PNG como CTkImage (ou None se falhar)."""
    try:
        from PIL import Image
        for candidate in [
            os.path.join(ICON_DIR, f"{nome}_{size}.png"),
            os.path.join(ICON_DIR, f"{nome}.png"),
            os.path.join(BASE_DIR, "icons", f"{nome}_{size}.png"),
            os.path.join(BASE_DIR, "icons", f"{nome}.png"),
        ]:
            if os.path.isfile(candidate):
                im = Image.open(candidate).convert("RGBA")
                if im.size != (size, size):
                    im = im.resize((size, size), Image.Resampling.LANCZOS)
                return ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))
    except Exception as e:
        print(f"[icon] {nome}: {e}")
    return None


def carregar_icone_pil(nome: str, size: int = 64):
    """Carrega ícone como PIL Image (bandeja / iconphoto)."""
    try:
        from PIL import Image
        for candidate in [
            os.path.join(ICON_DIR, f"{nome}_{size}.png"),
            os.path.join(ICON_DIR, f"{nome}.png"),
        ]:
            if os.path.isfile(candidate):
                im = Image.open(candidate).convert("RGBA")
                if im.size != (size, size):
                    im = im.resize((size, size), Image.Resampling.LANCZOS)
                return im
    except Exception:
        pass
    return None

ROTAS = {
    "São Paulo (Direto)": {
        "base": 195, "var": 25,
        "hops": ["Portugal", "São Paulo"],
        "bgp_as": ["AS12345 PT-ISP", "AS1299 Arelion", "AS10429 Telefonica-BR", "AS AS-GAME-BR"],
        "bgp_path": "PT → EU-core → BR",
        "overlay_path": "PT → edge SP",
        "bgp_ping": 210,
    },
    "Madrid → São Paulo": {
        "base": 175, "var": 18,
        "hops": ["Portugal", "Madrid", "São Paulo"],
        "bgp_as": ["AS12345 PT-ISP", "AS3352 Telefonica-ES", "AS10429 Telefonica-BR", "AS-GAME-BR"],
        "bgp_path": "PT → ES → BR",
        "overlay_path": "PT → MAD-node → SP-node → Game",
        "bgp_ping": 195,
    },
    "Londres → São Paulo": {
        "base": 185, "var": 20,
        "hops": ["Portugal", "Londres", "São Paulo"],
        "bgp_as": ["AS12345 PT-ISP", "AS174 Cogent", "AS3356 Level3", "AS-GAME-BR"],
        "bgp_path": "PT → UK → US-backbone → BR",
        "overlay_path": "PT → LON-node → SP-node → Game",
        "bgp_ping": 205,
    },
    "Frankfurt → São Paulo": {
        "base": 190, "var": 22,
        "hops": ["Portugal", "Frankfurt", "São Paulo"],
        "bgp_as": ["AS12345 PT-ISP", "AS3320 DeutscheTelekom", "AS1299 Arelion", "AS-GAME-BR"],
        "bgp_path": "PT → DE → EU-IX → BR",
        "overlay_path": "PT → FRA-node → SP-node → Game",
        "bgp_ping": 200,
    },
    "Miami → São Paulo": {
        "base": 210, "var": 28,
        "hops": ["Portugal", "Miami", "São Paulo"],
        "bgp_as": ["AS12345 PT-ISP", "AS3356 Level3", "AS16509 Amazon", "AS-GAME-BR"],
        "bgp_path": "PT → US-East → Miami → BR",
        "overlay_path": "PT → MIA-node → SP-node → Game",
        "bgp_ping": 230,
    },
}

# Cyberpunk / Neon palette
TEMAS = {
    "Ciano Neon": {"accent": "#00f0ff", "hover": "#00c4d6"},
    "Magenta": {"accent": "#ff2bd6", "hover": "#d916b0"},
    "Verde Matrix": {"accent": "#39ff14", "hover": "#2bd610"},
    "Roxo Neon": {"accent": "#b026ff", "hover": "#8b1ad1"},
    "Laranja Plasma": {"accent": "#ff6b00", "hover": "#e05a00"},
}

COR_FUNDO = "#060b12"
COR_CARD = "#0a121c"
COR_CARD2 = "#12121c"
COR_VERMELHO = "#ff0055"
COR_LARANJA = "#ffb800"
COR_TEXTO = "#e8f6ff"
COR_SEC = "#6b7c8a"
COR_BORDA = "#1e3a4c"
COR_GLOW = "#00f0ff"
# Sondas UDP (DNS) + fallback ICMP
UDP_DNS_TARGETS = [
    ("1.1.1.1", 53),
    ("8.8.8.8", 53),
    ("8.8.4.4", 53),
    ("208.67.222.222", 53),
]
ICMP_HOSTS = ["1.1.1.1", "8.8.8.8", "www.google.com.br"]


def _build_dns_query(domain="www.google.com.br"):
    import random as _rnd
    txid = _rnd.randint(0, 65535)
    header = txid.to_bytes(2, "big") + bytes([0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    q = b""
    for label in domain.split("."):
        q += bytes([len(label)]) + label.encode("ascii")
    q += bytes([0x00, 0x00, 0x01, 0x00, 0x01])
    return header + q


def medir_udp_dns(host, port=53, timeout=1.5):
    """RTT via UDP DNS query (protocolo usado por muitos jogos/servicos)."""
    import socket, time
    sock = None
    try:
        payload = _build_dns_query()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        t0 = time.perf_counter()
        sock.sendto(payload, (host, port))
        data, _addr = sock.recvfrom(512)
        t1 = time.perf_counter()
        if data and len(data) >= 12:
            return max(1, int((t1 - t0) * 1000))
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return None


def medir_udp_media():
    """Mediana de varias sondas UDP DNS."""
    results = []
    for host, port in UDP_DNS_TARGETS:
        rtt = medir_udp_dns(host, port)
        if rtt is not None:
            results.append(rtt)
        if len(results) >= 3:
            break
    if not results:
        return None
    results.sort()
    return results[len(results) // 2]


# Portas TCP tipicas de servicos / jogos (handshake SYN-ACK mede RTT)
TCP_TARGETS = [
    ("1.1.1.1", 443),
    ("8.8.8.8", 443),
    ("www.google.com.br", 443),
    ("www.cloudflare.com", 443),
]


def medir_tcp_rtt(host, port=443, timeout=1.5):
    """RTT aproximado via handshake TCP (connect)."""
    import socket, time
    try:
        # resolve se for hostname
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return None
        addr = infos[0][4]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        t0 = time.perf_counter()
        sock.connect(addr)
        t1 = time.perf_counter()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        sock.close()
        return max(1, int((t1 - t0) * 1000))
    except Exception:
        try:
            sock.close()
        except Exception:
            pass
        return None


def medir_tcp_media():
    results = []
    for host, port in TCP_TARGETS:
        rtt = medir_tcp_rtt(host, port)
        if rtt is not None:
            results.append(rtt)
        if len(results) >= 2:
            break
    if not results:
        return None
    results.sort()
    return results[len(results) // 2]


def multi_probe():
    """
    Sonda combinada UDP + TCP.
    Devolve dict: {udp, tcp, combined, method}
    """
    udp = medir_udp_media()
    tcp = medir_tcp_media()
    samples = [x for x in (udp, tcp) if x is not None]
    if not samples:
        return {"udp": None, "tcp": None, "combined": None, "method": None}
    samples.sort()
    combined = samples[len(samples) // 2]
    if udp is not None and tcp is not None:
        method = "UDP+TCP"
    elif udp is not None:
        method = "UDP"
    else:
        method = "TCP"
    return {"udp": udp, "tcp": tcp, "combined": combined, "method": method}


def criar_fundo_exitlag(width=900, height=1000):
    """Fundo escuro estilo ExitLag: gradiente + grelha de rede subtil."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return None
    img = Image.new("RGB", (width, height), (5, 8, 16))
    draw = ImageDraw.Draw(img, "RGBA")
    # Gradiente vertical (topo mais claro/azul)
    for y in range(height):
        t = y / height
        r = int(5 + t * 3)
        g = int(8 + t * 6)
        b = int(18 + (1 - t) * 22)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    # Grelha subtil
    step = 48
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=(0, 80, 120, 28))
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=(0, 80, 120, 28))
    # Nós / pontos de rede
    import random as _r
    _r.seed(42)
    points = [(_r.randint(20, width - 20), _r.randint(20, height - 20)) for _ in range(28)]
    for i, (x, y) in enumerate(points):
        # conexões leves
        for j in range(i + 1, min(i + 4, len(points))):
            x2, y2 = points[j]
            dist = ((x - x2) ** 2 + (y - y2) ** 2) ** 0.5
            if dist < 180:
                draw.line([(x, y), (x2, y2)], fill=(0, 180, 220, 35), width=1)
        r = 2 if i % 3 else 3
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(0, 220, 255, 90))
    # Glow suave no centro-topo
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = width // 2, 80
    for rad, alpha in [(220, 25), (140, 40), (70, 55)]:
        gd.ellipse([cx - rad, cy - rad // 2, cx + rad, cy + rad // 2], fill=(0, 150, 200, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    return img

TR = {
    "pt": {
        "title": "OptiLag • PT → BR", "off": "● Desconectado", "on": "● Otimizando",
        "connecting": "● Conectando...", "game": "JOGO", "route": "ROTA", "stats": "ESTATÍSTICAS",
        "ping": "PING", "real": "PING REAL", "loss": "LOSS", "gain": "MELHORIA",
        "start": "▶  OTIMIZAR", "stop": "⏹  PARAR", "test": "🔍 Testar", "settings": "Configurações",
        "history": "Histórico", "overlay": "Overlay", "export": "Exportar", "save": "Salvar", "close": "Fechar",
        "start_win": "Iniciar com Windows", "tray": "Minimizar p/ bandeja", "sound": "Sons",
        "comp": "Modo Competitivo", "compact": "Modo Compacto", "graph": "Mostrar gráfico",
        "aot": "Sempre no topo", "lang": "Idioma", "theme": "Tema", "session": "Sessão",
        "total": "Total otimizado", "detect": "Jogo detetado", "no_game": "Nenhum jogo detetado",
        "before": "Antes", "after": "Depois", "trace": "Rota", "notif_on": "Otimização ativada",
        "notif_off": "Otimização desativada", "high": "⚠ Ping alto", "recommended": "Madrid → São Paulo recomendado",
        "c1": "Conectando ao nó...", "c2": "Medindo rotas...", "c3": "Escolhendo caminho...", "c4": "Rota pronta!",
        "login": "Entrar", "user": "Utilizador", "pass": "Palavra-passe", "remember": "Lembrar sessão",
        "activate": "Ativar licença", "license_key": "Chave de licença", "admin_panel": "Painel Admin",
        "gen_key": "Gerar chave", "users": "Utilizadores", "create_user": "Criar utilizador",
        "remove_user": "Remover", "logout": "Sair da conta", "setup": "Configuração inicial",
        "admin_pass": "Palavra-passe do Admin", "confirm": "Confirmar", "invalid": "Credenciais inválidas",
        "need_license": "Precisas de uma licença válida", "key_ok": "Licença ativada!", "key_bad": "Chave inválida",
        "welcome": "Bem-vindo",
    },
    "en": {
        "title": "OptiLag • PT → BR", "off": "● Disconnected", "on": "● Optimizing",
        "connecting": "● Connecting...", "game": "GAME", "route": "ROUTE", "stats": "STATS",
        "ping": "PING", "real": "REAL PING", "loss": "LOSS", "gain": "GAIN",
        "start": "▶  OPTIMIZE", "stop": "⏹  STOP", "test": "🔍 Test", "settings": "Settings",
        "history": "History", "overlay": "Overlay", "export": "Export", "save": "Save", "close": "Close",
        "start_win": "Start with Windows", "tray": "Minimize to tray", "sound": "Sounds",
        "comp": "Competitive Mode", "compact": "Compact Mode", "graph": "Show graph",
        "aot": "Always on top", "lang": "Language", "theme": "Theme", "session": "Session",
        "total": "Total optimized", "detect": "Game detected", "no_game": "No game detected",
        "before": "Before", "after": "After", "trace": "Route", "notif_on": "Optimization on",
        "notif_off": "Optimization off", "high": "⚠ High ping", "recommended": "Madrid → São Paulo recommended",
        "c1": "Connecting to node...", "c2": "Measuring routes...", "c3": "Selecting path...", "c4": "Route ready!",
        "login": "Login", "user": "Username", "pass": "Password", "remember": "Remember session",
        "activate": "Activate license", "license_key": "License key", "admin_panel": "Admin Panel",
        "gen_key": "Generate key", "users": "Users", "create_user": "Create user",
        "remove_user": "Remove", "logout": "Logout", "setup": "Initial setup",
        "admin_pass": "Admin password", "confirm": "Confirm", "invalid": "Invalid credentials",
        "need_license": "Valid license required", "key_ok": "License activated!", "key_bad": "Invalid key",
        "welcome": "Welcome",
    },
}


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def gen_license_key() -> str:
    parts = []
    for _ in range(4):
        parts.append("".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)))
    return "-".join(parts)


def default_config():
    return {
        "idioma": "pt", "tema": "Ciano Neon", "iniciar_windows": False, "bandeja": True,
        "som": True, "competitivo": False, "compacto": False, "grafico": False,
        "always_on_top": False, "jogo": "PUBG: Battlegrounds", "rota": "Madrid → São Paulo",
        "perfis": {}, "favoritos": ["Madrid → São Paulo"], "tempo_total_seg": 0,

    }


def default_auth():
    return {
        "users": {},
        "licenses": {},
        "session": {"user": None, "remember": False},
        "setup_done": False,
    }


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default if not callable(default) else default()


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ==================== AUTH / LOGIN ====================
class AuthManager:
    def __init__(self):
        self.data = load_json(AUTH_FILE, default_auth())
        if "users" not in self.data:
            self.data = default_auth()

    def save(self):
        save_json(AUTH_FILE, self.data)

    def setup_done(self):
        return self.data.get("setup_done", False)

    def create_admin(self, password: str):
        key = gen_license_key()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.data["users"]["admin"] = {
            "password": hash_pw(password),
            "role": "admin",
            "license": key,
            "active": True,
            "created_at": now,
            "last_login": None,
        }
        self.data["licenses"][key] = {
            "used_by": "admin",
            "created": now,
            "active": True,
        }
        self.data["setup_done"] = True
        self.save()
        return key

    def login(self, username: str, password: str) -> tuple:
        user = self.data["users"].get(username)
        if not user:
            return False, "invalid"
        if user.get("password") != hash_pw(password):
            return False, "invalid"
        if not user.get("active", True):
            return False, "inactive"
        # Admin não precisa de licença extra; user normal precisa de licença ativa
        if user.get("role") != "admin":
            lic = user.get("license")
            if not lic or lic not in self.data["licenses"] or not self.data["licenses"][lic].get("active"):
                return False, "need_license"
        # Atualiza último acesso
        user["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if "created_at" not in user:
            user["created_at"] = user.get("last_login", "—")
        self.save()
        return True, user.get("role", "user")

    def set_session(self, username: str, remember: bool):
        self.data["session"] = {"user": username if remember else None, "remember": remember}
        self.save()

    def get_session(self):
        s = self.data.get("session", {})
        if s.get("remember") and s.get("user") and s["user"] in self.data["users"]:
            return s["user"]
        return None

    def clear_session(self):
        self.data["session"] = {"user": None, "remember": False}
        self.save()

    def generate_key(self) -> str:
        key = gen_license_key()
        self.data["licenses"][key] = {
            "used_by": None,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "active": True,
        }
        self.save()
        return key

    def activate_license(self, username: str, key: str) -> bool:
        key = key.strip().upper()
        lic = self.data["licenses"].get(key)
        if not lic or not lic.get("active"):
            return False
        if lic.get("used_by") and lic["used_by"] != username:
            return False
        user = self.data["users"].get(username)
        if not user:
            return False
        # Liberar key antiga do user
        old = user.get("license")
        if old and old in self.data["licenses"] and old != key:
            self.data["licenses"][old]["used_by"] = None
        user["license"] = key
        lic["used_by"] = username
        self.save()
        return True

    def create_user(self, username: str, password: str, license_key: str = None) -> str:
        if username in self.data["users"]:
            return "exists"
        if not username or not password:
            return "empty"
        key = license_key.strip().upper() if license_key else self.generate_key()
        if key not in self.data["licenses"]:
            self.data["licenses"][key] = {
                "used_by": username,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "active": True,
            }
        elif self.data["licenses"][key].get("used_by"):
            return "key_used"
        else:
            self.data["licenses"][key]["used_by"] = username

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.data["users"][username] = {
            "password": hash_pw(password),
            "role": "user",
            "license": key,
            "active": True,
            "created_at": now,
            "last_login": None,
        }
        self.save()
        return key

    def remove_user(self, username: str) -> bool:
        if username == "admin" or username not in self.data["users"]:
            return False
        user = self.data["users"].pop(username)
        lic = user.get("license")
        if lic and lic in self.data["licenses"]:
            self.data["licenses"][lic]["used_by"] = None
            # Opcional: desativar a key ao remover o user
            self.data["licenses"][lic]["active"] = False
        self.save()
        return True

    def get_user_info(self, username: str) -> dict:
        return self.data["users"].get(username, {})

    def revoke_key(self, key: str):
        if key in self.data["licenses"]:
            self.data["licenses"][key]["active"] = False
            self.save()

    def list_users(self):
        return list(self.data["users"].keys())

    def list_licenses(self):
        return self.data.get("licenses", {})


# ==================== JANELAS DE AUTH ====================
class SetupWindow(ctk.CTk):
    """Primeira execução: criar admin."""
    def __init__(self, auth: AuthManager):
        super().__init__()
        self.auth = auth
        self.result = None
        self.title("OptiLag — Setup")
        self.geometry("420x380")
        self.configure(fg_color=COR_FUNDO)
        self.resizable(False, False)

        ctk.CTkLabel(self, text="⚡ OptiLag", font=ctk.CTkFont(size=26, weight="bold"), text_color="#00f0ff").pack(pady=(30, 5))
        ctk.CTkLabel(self, text="Configuração inicial do Admin", font=ctk.CTkFont(size=14), text_color=COR_SEC).pack(pady=(0, 20))

        ctk.CTkLabel(self, text="Palavra-passe do Admin", text_color=COR_TEXTO).pack(anchor="w", padx=40)
        self.e1 = ctk.CTkEntry(self, show="•", width=320, height=36, fg_color="#21262d", border_color=COR_BORDA)
        self.e1.pack(pady=4)

        ctk.CTkLabel(self, text="Confirmar palavra-passe", text_color=COR_TEXTO).pack(anchor="w", padx=40, pady=(10, 0))
        self.e2 = ctk.CTkEntry(self, show="•", width=320, height=36, fg_color="#21262d", border_color=COR_BORDA)
        self.e2.pack(pady=4)

        self.msg = ctk.CTkLabel(self, text="", text_color=COR_VERMELHO)
        self.msg.pack(pady=8)

        ctk.CTkButton(self, text="Criar conta Admin", width=320, height=40, fg_color="#00f0ff",
                      hover_color="#00c4d6", text_color="#0d1117", command=self._create).pack(pady=10)

    def _create(self):
        p1, p2 = self.e1.get(), self.e2.get()
        if len(p1) < 4:
            self.msg.configure(text="Mínimo 4 caracteres")
            return
        if p1 != p2:
            self.msg.configure(text="As palavras-passe não coincidem")
            return
        key = self.auth.create_admin(p1)
        self.result = ("admin", key)
        self.destroy()


class LoginWindow(ctk.CTk):
    def __init__(self, auth: AuthManager):
        super().__init__()
        self.auth = auth
        self.result_user = None
        self.result_role = None
        self.title("OptiLag — Login")
        self.geometry("400x420")
        self.configure(fg_color=COR_FUNDO)
        self.resizable(False, False)

        ctk.CTkLabel(self, text="⚡ OptiLag", font=ctk.CTkFont(size=26, weight="bold"), text_color="#00f0ff").pack(pady=(28, 5))
        ctk.CTkLabel(self, text="Inicia sessão para continuar", font=ctk.CTkFont(size=13), text_color=COR_SEC).pack(pady=(0, 18))

        ctk.CTkLabel(self, text="Utilizador", text_color=COR_TEXTO).pack(anchor="w", padx=40)
        self.e_user = ctk.CTkEntry(self, width=320, height=36, fg_color="#21262d", border_color=COR_BORDA)
        self.e_user.pack(pady=4)
        self.e_user.insert(0, "admin")

        ctk.CTkLabel(self, text="Palavra-passe", text_color=COR_TEXTO).pack(anchor="w", padx=40, pady=(8, 0))
        self.e_pass = ctk.CTkEntry(self, show="•", width=320, height=36, fg_color="#21262d", border_color=COR_BORDA)
        self.e_pass.pack(pady=4)

        self.remember = ctk.CTkCheckBox(self, text="Lembrar sessão", text_color=COR_SEC, fg_color="#00f0ff")
        self.remember.pack(pady=10)

        self.msg = ctk.CTkLabel(self, text="", text_color=COR_VERMELHO)
        self.msg.pack()

        ctk.CTkButton(self, text="Entrar", width=320, height=40, fg_color="#00f0ff",
                      hover_color="#00c4d6", text_color="#0d1117", command=self._login).pack(pady=8)

        ctk.CTkButton(self, text="Ativar licença", width=320, height=32, fg_color="#21262d",
                      hover_color="#30363d", command=self._activate_ui).pack()

        self.bind("<Return>", lambda e: self._login())

    def _login(self):
        u, p = self.e_user.get().strip(), self.e_pass.get()
        ok, info = self.auth.login(u, p)
        if not ok:
            msgs = {"invalid": "Utilizador ou palavra-passe incorretos",
                    "need_license": "Conta sem licença válida. Ativa uma chave.",
                    "inactive": "Conta desativada"}
            self.msg.configure(text=msgs.get(info, "Erro"))
            return
        self.auth.set_session(u, self.remember.get() == 1)
        self.result_user = u
        self.result_role = info
        self.destroy()

    def _activate_ui(self):
        win = ctk.CTkToplevel(self)
        win.title("Ativar licença")
        win.geometry("360x220")
        win.configure(fg_color=COR_FUNDO)
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text="Utilizador", text_color=COR_TEXTO).pack(anchor="w", padx=30, pady=(20, 0))
        eu = ctk.CTkEntry(win, width=280, height=32, fg_color="#21262d")
        eu.pack()
        ctk.CTkLabel(win, text="Chave de licença", text_color=COR_TEXTO).pack(anchor="w", padx=30, pady=(10, 0))
        ek = ctk.CTkEntry(win, width=280, height=32, fg_color="#21262d")
        ek.pack()
        lm = ctk.CTkLabel(win, text="", text_color=COR_VERMELHO)
        lm.pack(pady=6)

        def go():
            if self.auth.activate_license(eu.get().strip(), ek.get()):
                lm.configure(text="Licença ativada!", text_color="#00f0ff")
                win.after(800, win.destroy)
            else:
                lm.configure(text="Chave inválida ou já usada")
        ctk.CTkButton(win, text="Ativar", width=280, height=34, fg_color="#00f0ff",
                      hover_color="#00c4d6", text_color="#0d1117", command=go).pack(pady=8)


# ==================== APP PRINCIPAL ====================
class OptiLagApp(ctk.CTk):
    def __init__(self, auth: AuthManager, username: str, role: str):
        super().__init__()
        self.auth = auth
        self.username = username
        self.role = role
        self.cfg = load_json(CONFIG_FILE, default_config())
        if not isinstance(self.cfg, dict):
            self.cfg = default_config()
        for k, v in default_config().items():
            self.cfg.setdefault(k, v)

        self.t = TR.get(self.cfg["idioma"], TR["pt"])
        self.accent = TEMAS.get(self.cfg["tema"], TEMAS["Ciano Neon"])["accent"]
        self.hover = TEMAS.get(self.cfg["tema"], TEMAS["Ciano Neon"])["hover"]

        self.otimizando = False
        self.conectando = False
        self.ping_atual = 0
        self.ping_real = 0
        self.ping_antes = 0
        self.loss = 0.0
        self.inicio = None
        self.historico = load_json(HISTORY_FILE, [])
        self.tray_icon = None
        self.overlay_win = None
        self.graph_data = []
        self.graph_data_real = []
        self._probe_detail = {}
        self._last_probe = None
        self._ping_lock = threading.Lock()
        self.jogo = self.cfg.get("jogo", "PUBG: Battlegrounds")
        self.rota = self.cfg.get("rota", "Madrid → São Paulo")

        self.title(f"{self.t['title']}  |  {username}")
        self.geometry("560x840")
        self.minsize(500, 580)
        self.configure(fg_color=COR_FUNDO)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_window_icon()
        self._icon_cache = {}
        if self.cfg.get("always_on_top"):
            self.attributes("-topmost", True)

        self.bind("<Control-Shift-O>", lambda e: self._toggle())
        self._build_ui()
        self._start_loops()

    def _save_cfg(self):
        self.cfg["jogo"] = self.jogo
        self.cfg["rota"] = self.rota
        save_json(CONFIG_FILE, self.cfg)

    def _measure_ping(self):
        """Multi-probe via backend (UDP+TCP) com fallback local."""
        if HAS_BACKEND:
            try:
                result = probe_now()
                self._last_probe = result.method
                self._probe_detail = {
                    "udp": result.udp,
                    "tcp": result.tcp,
                    "combined": result.combined,
                    "method": result.method,
                }
                return result.combined
            except Exception as e:
                print(f"[backend probe] {e}")
        # fallback: funções locais se existirem
        try:
            result = multi_probe()
            if isinstance(result, dict):
                self._probe_detail = result
                self._last_probe = result.get("method")
                return result.get("combined")
            # ProbeResult object from local copy
            self._last_probe = getattr(result, "method", None)
            self._probe_detail = {
                "udp": getattr(result, "udp", None),
                "tcp": getattr(result, "tcp", None),
                "combined": getattr(result, "combined", None),
                "method": getattr(result, "method", None),
            }
            return getattr(result, "combined", None)
        except Exception:
            pass
        return None

    def _build_ui(self):
        # --- Camada de fundo (Canvas) + conteúdo por cima ---
        import tkinter as tk
        self._bg_label = None
        self._bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg="#05050a")
        self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content.place(x=0, y=0, relwidth=1, relheight=1)

        self.bind("<Configure>", self._on_resize_bg)
        self.after(150, self._aplicar_fundo)

        hdr = ctk.CTkFrame(self.content, fg_color=COR_CARD, height=62, corner_radius=0, border_width=1, border_color=COR_BORDA)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        # Logo cyberpunk
        logo_box = ctk.CTkFrame(hdr, fg_color="transparent")
        logo_box.pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(logo_box, text="⚡ OPTILAG", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.accent).pack(anchor="w")
        ctk.CTkLabel(logo_box, text=f"// NETWORK OPTIMIZER  v{APP_VERSION}", font=ctk.CTkFont(size=9), text_color=COR_SEC).pack(anchor="w")

        # User badge
        ctk.CTkLabel(hdr, text=f"[{self.username.upper()}]", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.accent).pack(side="left", padx=8)

        btns = [("Overlay", self._toggle_overlay), ("📜", self._open_history), ("⚙", self._open_settings)]
        if self.role == "admin":
            btns.insert(0, ("Admin", self._open_admin))
        for txt, cmd in btns:
            w = 56 if len(txt) > 2 else 34
            ctk.CTkButton(hdr, text=txt, width=w, height=30, fg_color="#21262d", hover_color="#30363d", command=cmd).pack(side="right", padx=2, pady=14)

        self.lbl_status = ctk.CTkLabel(hdr, text=self.t["off"], font=ctk.CTkFont(size=11), text_color=COR_VERMELHO)
        self.lbl_status.pack(side="right", padx=4)

        self.main = ctk.CTkScrollableFrame(self.content, fg_color="transparent", corner_radius=0)
        self.main.pack(fill="both", expand=True, padx=12, pady=8)

        # Banner visual estilo ExitLag (sempre visível)
        self.banner_frame = ctk.CTkFrame(self.main, fg_color="#071018", corner_radius=6, border_width=1, border_color="#0a4a5c", height=110)
        self.banner_frame.pack(fill="x", pady=(0, 10))
        self.banner_frame.pack_propagate(False)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="")
        self.banner_label.pack(fill="both", expand=True)
        self._atualizar_banner()

        self.lbl_detect = ctk.CTkLabel(self.main, text=self.t["no_game"], font=ctk.CTkFont(size=11), text_color=COR_SEC)
        self.lbl_detect.pack(anchor="w", pady=(0, 4))

        self.card_game = self._card()
        ctk.CTkLabel(self.card_game, text=self.t["game"], font=ctk.CTkFont(size=10, weight="bold"), text_color=COR_SEC).pack(anchor="w", padx=10, pady=(8, 2))
        game_row = ctk.CTkFrame(self.card_game, fg_color="transparent")
        game_row.pack(fill="x", padx=10, pady=(0, 8))
        self.lbl_game_icon = ctk.CTkLabel(game_row, text="", width=36, height=36)
        self.lbl_game_icon.pack(side="left", padx=(0, 8))
        self.combo_jogo = ctk.CTkComboBox(game_row, values=list(JOGOS.keys()), width=440, height=32,
                                          fg_color="#21262d", border_color=COR_BORDA, button_color=self.accent, command=self._on_game)
        self.combo_jogo.set(self.jogo)
        self.combo_jogo.pack(side="left", fill="x", expand=True)
        self._atualizar_icone_jogo(self.jogo)
        self._aplicar_cor_jogo(self.jogo)

        self.card_route = self._card()
        route_hdr = ctk.CTkFrame(self.card_route, fg_color="transparent")
        route_hdr.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(route_hdr, text=self.t["route"], font=ctk.CTkFont(size=10, weight="bold"), text_color=COR_SEC).pack(side="left")
        self.btn_fav = ctk.CTkButton(route_hdr, text="☆ Favorito", width=90, height=24, fg_color="#21262d",
                                     hover_color="#30363d", font=ctk.CTkFont(size=11), command=self._toggle_fav)
        self.btn_fav.pack(side="right")

        self.combo_rota = ctk.CTkComboBox(self.card_route, values=list(ROTAS.keys()), width=500, height=30,
                                          fg_color="#21262d", border_color=COR_BORDA, button_color=self.accent, command=self._on_route)
        self.combo_rota.set(self.rota)
        self.combo_rota.pack(padx=10, pady=(0, 4))

        # Mapa visual da rota (nós)
        self.map_frame = ctk.CTkFrame(self.card_route, fg_color="#0d1117", corner_radius=8, height=52)
        self.map_frame.pack(fill="x", padx=10, pady=(0, 4))
        self.map_frame.pack_propagate(False)
        self.hop_labels = []
        self._rebuild_route_map()

        self.lbl_trace = ctk.CTkLabel(self.card_route, text="", font=ctk.CTkFont(size=10), text_color=COR_SEC)
        self.lbl_trace.pack(anchor="w", padx=10, pady=(0, 2))
        self.lbl_smart = ctk.CTkLabel(self.card_route, text="", font=ctk.CTkFont(size=11), text_color=self.accent, wraplength=480, justify="left")
        self.lbl_smart.pack(anchor="w", padx=10, pady=(0, 4))

        # Comparação BGP vs Overlay
        self.bgp_frame = ctk.CTkFrame(self.card_route, fg_color="#071018", corner_radius=6, border_width=1, border_color=COR_BORDA)
        self.bgp_frame.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(self.bgp_frame, text="🌐  BGP (ISP)  vs  ⚡ Overlay", font=ctk.CTkFont(size=10, weight="bold"), text_color=COR_SEC).pack(anchor="w", padx=8, pady=(6, 2))
        self.lbl_bgp = ctk.CTkLabel(self.bgp_frame, text="", font=ctk.CTkFont(size=11), text_color=COR_LARANJA, wraplength=480, justify="left")
        self.lbl_bgp.pack(anchor="w", padx=8, pady=1)
        self.lbl_overlay = ctk.CTkLabel(self.bgp_frame, text="", font=ctk.CTkFont(size=11), text_color="#00f0ff", wraplength=480, justify="left")
        self.lbl_overlay.pack(anchor="w", padx=8, pady=1)
        self.lbl_bgp_as = ctk.CTkLabel(self.bgp_frame, text="", font=ctk.CTkFont(size=10), text_color=COR_SEC, wraplength=480, justify="left")
        self.lbl_bgp_as.pack(anchor="w", padx=8, pady=(1, 6))

        self._update_fav_btn()
        self._update_smart_tip()
        self._update_bgp_panel()

        self.card_stats = self._card()
        ctk.CTkLabel(self.card_stats, text=self.t["stats"], font=ctk.CTkFont(size=10, weight="bold"), text_color=COR_SEC).pack(anchor="w", padx=10, pady=(8, 4))
        g = ctk.CTkFrame(self.card_stats, fg_color="transparent")
        g.pack(fill="x", padx=6)
        self.lbl_ping = self._stat(g, self.t["ping"], "--", 0, 0)
        self.lbl_real = self._stat(g, self.t["real"], "--", 0, 1)
        self.lbl_loss = self._stat(g, self.t["loss"], "--", 1, 0)
        self.lbl_gain = self._stat(g, self.t["gain"], "--", 1, 1)
        cmpf = ctk.CTkFrame(self.card_stats, fg_color="#21262d", corner_radius=6)
        cmpf.pack(fill="x", padx=8, pady=(4, 8))
        self.lbl_before = ctk.CTkLabel(cmpf, text=f"{self.t['before']}: --", font=ctk.CTkFont(size=11), text_color=COR_LARANJA)
        self.lbl_before.pack(side="left", padx=8, pady=5)
        self.lbl_after = ctk.CTkLabel(cmpf, text=f"{self.t['after']}: --", font=ctk.CTkFont(size=11), text_color=self.accent)
        self.lbl_after.pack(side="right", padx=8, pady=5)

        # Indicador de qualidade do ping
        self.lbl_quality = ctk.CTkLabel(
            self.card_stats, text="● Qualidade: —",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_SEC
        )
        self.lbl_quality.pack(anchor="w", padx=12, pady=(0, 8))

        self.graph_frame = ctk.CTkFrame(self.main, fg_color=COR_CARD, corner_radius=8, border_width=1, border_color=COR_BORDA)
        if HAS_GRAPH:
            self.fig = Figure(figsize=(5, 1.6), dpi=100, facecolor=COR_CARD)
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor("#0d1117")
            self.ax.tick_params(colors=COR_SEC, labelsize=6)
            for sp in self.ax.spines.values():
                sp.set_color(COR_BORDA)
            self.line, = self.ax.plot([], [], color=self.accent, lw=1.4, label="Ping")
            self.line_real, = self.ax.plot([], [], color="#4aa3ff", lw=1.2, linestyle="--", label="Real UDP/TCP")
            try:
                self.ax.legend(loc="upper right", fontsize=7, facecolor="#0a121c", edgecolor="#1e3a4c", labelcolor="#e8f6ff")
            except Exception:
                pass
            self.fig.tight_layout(pad=0.6)
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
            self.canvas.get_tk_widget().pack(fill="x", padx=6, pady=6)

        self.btn_opt = ctk.CTkButton(self.main, text=self.t["start"], font=ctk.CTkFont(size=15, weight="bold"),
                                     height=48, corner_radius=4, fg_color=self.accent, hover_color=self.hover,
                                     text_color="#05050a", border_width=2, border_color=self.accent, command=self._toggle)
        self.btn_opt.pack(fill="x", pady=(6, 3))
        self.btn_test = ctk.CTkButton(self.main, text=self.t["test"], height=30, fg_color="#21262d", hover_color="#30363d", command=self._test)
        self.btn_test.pack(fill="x", pady=(0, 4))

        self.progress = ctk.CTkProgressBar(self.main, height=6, progress_color=self.accent, fg_color="#1a1a2e")
        self.progress.set(0)
        self.lbl_conn = ctk.CTkLabel(self.main, text="", font=ctk.CTkFont(size=11), text_color=self.accent)
        self.lbl_info = ctk.CTkLabel(self.main, text=self.t["recommended"], font=ctk.CTkFont(size=11), text_color=COR_SEC)
        self.lbl_info.pack()
        self.lbl_session = ctk.CTkLabel(self.main, text=f"{self.t['session']}: --", font=ctk.CTkFont(size=11), text_color=COR_SEC)
        self.lbl_session.pack()
        self.lbl_total = ctk.CTkLabel(self.main, text=f"{self.t['total']}: {self._fmt_total()}", font=ctk.CTkFont(size=11), text_color=COR_SEC)
        self.lbl_total.pack()
        self.lbl_alert = ctk.CTkLabel(self.main, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color=COR_VERMELHO)
        self.lbl_alert.pack()



        # --- Painel Backend / API ---
        self.card_backend = self._card()
        bh = ctk.CTkFrame(self.card_backend, fg_color="transparent")
        bh.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(bh, text="BACKEND / API", font=ctk.CTkFont(size=10, weight="bold"), text_color=COR_SEC).pack(side="left")
        ctk.CTkButton(bh, text="Atualizar", width=80, height=24, fg_color="#21262d", hover_color="#30363d",
                      command=self._refresh_backend_panel).pack(side="right")
        self.lbl_api_status = ctk.CTkLabel(self.card_backend, text="API: —", font=ctk.CTkFont(size=11), text_color=COR_SEC)
        self.lbl_api_status.pack(anchor="w", padx=10, pady=1)
        self.lbl_be_stats = ctk.CTkLabel(self.card_backend, text="Stats: —", font=ctk.CTkFont(size=11), text_color=COR_TEXTO)
        self.lbl_be_stats.pack(anchor="w", padx=10, pady=1)
        self.lbl_be_sessions = ctk.CTkLabel(self.card_backend, text="Sessões: —", font=ctk.CTkFont(size=11), text_color=COR_SEC, wraplength=480, justify="left")
        self.lbl_be_sessions.pack(anchor="w", padx=10, pady=(1, 8))
        self.after(1500, self._refresh_backend_panel)

        ctk.CTkButton(self.main, text=self.t["logout"], height=28, fg_color="#21262d", hover_color=COR_VERMELHO,
                      command=self._logout).pack(pady=(12, 4))

        if self.cfg.get("grafico") and HAS_GRAPH:
            self.graph_frame.pack(fill="x", pady=(6, 0), before=self.btn_opt)

        def _bg_boot():
            self._aplicar_fundo()
        self.after(100, _bg_boot)
        # Backend sampler
        if HAS_BACKEND:
            try:
                get_sampler()
            except Exception as e:
                print(f"[backend sampler] {e}")
        self.after(400, _bg_boot)

    def _card(self):
        f = ctk.CTkFrame(self.main, fg_color=COR_CARD, corner_radius=4, border_width=1, border_color=COR_BORDA)
        f.pack(fill="x", pady=(0, 6))
        return f

    def _aplicar_fundo(self):
        """Desenha fundo estilo ExitLag no canvas de trás."""
        try:
            import tkinter as tk
            from PIL import ImageTk
            if not hasattr(self, "_bg_canvas"):
                return
            w = self.winfo_width()
            h = self.winfo_height()
            if w < 200:
                w = 900
            if h < 200:
                h = 1000
            w = min(max(w, 600), 1600)
            h = min(max(h, 600), 1200)
            img = criar_fundo_exitlag(w, h)
            if img is None:
                return
            self._bg_img = ImageTk.PhotoImage(img)
            self._bg_canvas.delete("all")
            self._bg_canvas.configure(width=w, height=h)
            self._bg_canvas.create_image(0, 0, anchor="nw", image=self._bg_img)
            self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            # Canvas.lower() é para items — usar tk.call para stacking da janela
            try:
                self._bg_canvas.tk.call("lower", self._bg_canvas._w)
            except Exception:
                pass
            if hasattr(self, "content"):
                try:
                    self.content.tk.call("raise", self.content._w)
                except Exception:
                    try:
                        self.content.lift()
                    except Exception:
                        pass
        except Exception as e:
            print(f"[fundo] erro: {e}")


    def _atualizar_banner(self, jogo: str = None):
        """Banner estilo ExitLag com OPTILAG + ícone e nome do jogo."""
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageFilter
            w, h = 520, 110
            img = criar_fundo_exitlag(w, h)
            if img is None:
                raise RuntimeError("sem imagem")
            img = img.convert("RGBA")
            draw = ImageDraw.Draw(img)
            draw.rectangle([1, 1, w - 2, h - 2], outline=(0, 200, 230, 120), width=1)

            jogo = jogo or getattr(self, "jogo", "PUBG: Battlegrounds")
            icon_key = JOGOS.get(jogo, {}).get("icon", "optilag")

            font_big = font_sub = font_game = None
            for fp in [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]:
                try:
                    font_big = ImageFont.truetype(fp, 28)
                    font_sub = ImageFont.truetype(fp, 11)
                    font_game = ImageFont.truetype(fp, 13)
                    break
                except Exception:
                    continue
            if font_big is None:
                font_big = ImageFont.load_default()
                font_sub = font_game = font_big

            # Ícone do jogo à esquerda
            icon_im = carregar_icone_pil(icon_key, 64)
            if icon_im is not None:
                icon_im = icon_im.convert("RGBA").resize((56, 56), Image.Resampling.LANCZOS)
                img.paste(icon_im, (18, (h - 56) // 2), icon_im)

            title = "OPTILAG"
            subtitle = "PT  →  BR  •  NETWORK OPTIMIZER"
            game_line = jogo

            # Texto centrado (deslocado um pouco à direita por causa do ícone)
            def text_size(text, font):
                try:
                    b = draw.textbbox((0, 0), text, font=font)
                    return b[2] - b[0], b[3] - b[1]
                except Exception:
                    return len(text) * 8, 16

            tw, th = text_size(title, font_big)
            sw, sh = text_size(subtitle, font_sub)
            gw, gh = text_size(game_line, font_game)

            tx = (w - tw) // 2 + 20
            ty = 18
            sx = (w - sw) // 2 + 20
            gx = (w - gw) // 2 + 20

            glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                gd.text((tx + dx, ty + dy), title, font=font_big, fill=(0, 240, 255, 60))
            glow = glow.filter(ImageFilter.GaussianBlur(radius=2))
            img = Image.alpha_composite(img, glow)
            draw = ImageDraw.Draw(img)

            draw.text((tx, ty), title, font=font_big, fill=(0, 245, 255, 255))
            draw.text((sx, ty + th + 4), subtitle, font=font_sub, fill=(140, 200, 220, 220))
            draw.text((gx, ty + th + sh + 10), game_line, font=font_game, fill=(200, 255, 240, 255))

            img_rgb = img.convert("RGB")
            try:
                self._banner_ctk = ctk.CTkImage(light_image=img_rgb, dark_image=img_rgb, size=(w, h))
                self.banner_label.configure(image=self._banner_ctk, text="")
            except Exception:
                from PIL import ImageTk
                self._banner_img = ImageTk.PhotoImage(img_rgb)
                self.banner_label.configure(image=self._banner_img, text="")
        except Exception as e:
            print(f"[banner] erro: {e}")
            try:
                j = jogo if "jogo" in dir() else "..."
                self.banner_label.configure(
                    text=f"OPTILAG  |  {j}",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color="#00f0ff",
                )
            except Exception:
                pass

    def _on_resize_bg(self, event=None):
        if event is not None and event.widget is not self:
            return
        if not hasattr(self, "_bg_resize_after"):
            self._bg_resize_after = None
        if self._bg_resize_after:
            try:
                self.after_cancel(self._bg_resize_after)
            except Exception:
                pass
        self._bg_resize_after = self.after(400, self._aplicar_fundo)

    def _stat(self, parent, title, val, r, c):
        f = ctk.CTkFrame(parent, fg_color="#21262d", corner_radius=6)
        f.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
        parent.grid_columnconfigure(c, weight=1)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=9), text_color=COR_SEC).pack(pady=(4, 0))
        lbl = ctk.CTkLabel(f, text=val, font=ctk.CTkFont(size=14, weight="bold"), text_color=COR_TEXTO)
        lbl.pack(pady=(0, 4))
        return lbl


    def _set_window_icon(self):
        """Define ícone da janela (Windows/Linux)."""
        try:
            from PIL import ImageTk
            im = carregar_icone_pil("optilag", 64)
            if im is None:
                return
            self._win_icon = ImageTk.PhotoImage(im)
            self.iconphoto(True, self._win_icon)
        except Exception as e:
            print(f"[icon] window: {e}")

    def _atualizar_icone_jogo(self, nome_jogo: str):
        """Atualiza o ícone ao lado do seletor de jogo."""
        try:
            info = JOGOS.get(nome_jogo, {})
            key = info.get("icon", "optilag")
            if not hasattr(self, "_icon_cache"):
                self._icon_cache = {}
            if key not in self._icon_cache:
                self._icon_cache[key] = carregar_icone(key, 32)
            img = self._icon_cache.get(key)
            if img is not None:
                self.lbl_game_icon.configure(image=img, text="")
            else:
                # fallback emoji do JOGOS antigo se existir
                self.lbl_game_icon.configure(image=None, text="🎮")
        except Exception as e:
            print(f"[icon] game: {e}")


    def _cor_jogo(self, nome=None):
        nome = nome or getattr(self, "jogo", None)
        info = JOGOS.get(nome or "", {})
        return info.get("cor", self.accent), info.get("cor_hover", self.hover)

    def _aplicar_cor_jogo(self, nome=None):
        """Ajusta accent da UI à cor do jogo selecionado."""
        try:
            cor, hover = self._cor_jogo(nome)
            self.accent = cor
            self.hover = hover
            if not self.otimizando:
                self.btn_opt.configure(fg_color=cor, hover_color=hover, border_color=cor, text_color="#05050a")
            self.combo_jogo.configure(button_color=cor)
            self.combo_rota.configure(button_color=cor)
            self.progress.configure(progress_color=cor)
            self.lbl_smart.configure(text_color=cor)
            self.lbl_after.configure(text_color=cor)
            self.lbl_conn.configure(text_color=cor)
            # Rebuild map nodes with new color
            if hasattr(self, "map_frame"):
                self._rebuild_route_map()
            self._update_fav_btn()
        except Exception as e:
            print(f"[theme-game] {e}")

    def _qualidade_ping(self, ping: int) -> tuple:
        """Devolve (texto, cor) conforme o ping PT→BR."""
        if ping <= 0:
            return "—", COR_SEC
        if ping < 100:
            return "Excelente", "#39ff14"
        if ping < 140:
            return "Muito bom", "#00f0ff"
        if ping < 180:
            return "Bom", "#decc4a"
        if ping < 220:
            return "Médio", "#ff9f1a"
        if ping < 280:
            return "Alto", "#ff4655"
        return "Muito alto", "#ff0055"


    def _api_get(self, path: str, timeout: float = 1.5):
        """GET JSON da API local http://127.0.0.1:8765"""
        url = f"http://127.0.0.1:8765{path}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _refresh_backend_panel(self):
        """Atualiza painel com stats/sessoes (API ou SQLite local)."""
        try:
            if not hasattr(self, "lbl_api_status"):
                return
            api_ok = False
            stats = None
            sessions = []
            try:
                health = self._api_get("/health")
                if health.get("ok"):
                    api_ok = True
                    stats = self._api_get("/stats")
                    sessions = self._api_get("/sessions?limit=5")
                    if isinstance(sessions, dict):
                        sessions = sessions.get("items", [])
            except Exception:
                api_ok = False

            if stats is None and HAS_BACKEND:
                try:
                    stats = backend_db.stats()
                    sessions = backend_db.recent_sessions(5)
                except Exception:
                    pass

            if api_ok:
                self.lbl_api_status.configure(text="API:  online  ·  127.0.0.1:8765", text_color="#39ff14")
            elif HAS_BACKEND:
                self.lbl_api_status.configure(text="API:  offline  ·  a usar SQLite local", text_color=COR_LARANJA)
            else:
                self.lbl_api_status.configure(text="API:  offline  ·  backend indisponível", text_color=COR_VERMELHO)

            if stats:
                avg = stats.get("avg_ping")
                avg_s = f"{avg} ms" if avg is not None else "—"
                self.lbl_be_stats.configure(
                    text=f"Stats:  {stats.get('probes', 0)} probes  ·  {stats.get('sessions', 0)} sessões  ·  avg {avg_s}"
                )
            else:
                self.lbl_be_stats.configure(text="Stats:  —")

            if sessions:
                lines = []
                for s in sessions[:3]:
                    route = s.get("route", "?")
                    dur = s.get("duration_sec", 0)
                    pb, pa = s.get("ping_before", "?"), s.get("ping_after", "?")
                    lines.append(f"• {route}  {pb}->{pa} ms  ({dur}s)")
                self.lbl_be_sessions.configure(text="Sessoes recentes:\n" + "\n".join(lines))
            else:
                self.lbl_be_sessions.configure(text="Sessoes:  nenhuma ainda")
        except Exception as e:
            print(f"[backend panel] {e}")

    def _fmt_total(self):
        s = int(self.cfg.get("tempo_total_seg", 0))
        h, m = divmod(s // 60, 60)
        return f"{h}h {m:02d}m"

    def _rebuild_route_map(self):
        for w in self.map_frame.winfo_children():
            w.destroy()
        self.hop_labels = []
        hops = ROTAS.get(self.rota, {}).get("hops", [])
        if not hops:
            return
        row = ctk.CTkFrame(self.map_frame, fg_color="transparent")
        row.pack(expand=True)
        for i, hop in enumerate(hops):
            node = ctk.CTkLabel(
                row, text=f"  {hop}  ",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#0d1117",
                fg_color=self.accent if i == 0 else "#30363d",
                corner_radius=6,
            )
            node.pack(side="left", padx=3, pady=10)
            self.hop_labels.append(node)
            if i < len(hops) - 1:
                ctk.CTkLabel(row, text="→", font=ctk.CTkFont(size=14, weight="bold"), text_color=COR_SEC).pack(side="left")

    def _animate_route_map(self, step=0):
        """Ilumina os nós da rota em sequência enquanto otimiza."""
        try:
            if not self.winfo_exists() or not self.otimizando and not self.conectando:
                # reset cores
                for i, lbl in enumerate(self.hop_labels):
                    lbl.configure(fg_color=self.accent if i == 0 else "#30363d", text_color="#0d1117" if i == 0 else COR_TEXTO)
                return
            n = len(self.hop_labels)
            if n == 0:
                return
            for i, lbl in enumerate(self.hop_labels):
                if i == step % n:
                    lbl.configure(fg_color=self.accent, text_color="#0d1117")
                else:
                    lbl.configure(fg_color="#21262d", text_color=COR_SEC)
            self.after(450, lambda: self._animate_route_map(step + 1))
        except Exception:
            pass

    def _toggle_fav(self):
        favs = self.cfg.setdefault("favoritos", [])
        if self.rota in favs:
            favs.remove(self.rota)
        else:
            favs.append(self.rota)
        self._save_cfg()
        self._update_fav_btn()
        self._update_smart_tip()

    def _update_fav_btn(self):
        favs = self.cfg.get("favoritos", [])
        if self.rota in favs:
            self.btn_fav.configure(text="★ Favorito", fg_color=self.accent, text_color="#0d1117")
        else:
            self.btn_fav.configure(text="☆ Favorito", fg_color="#21262d", text_color=COR_TEXTO)


    def _update_bgp_panel(self):
        """Mostra rota BGP (ISP) vs rota overlay otimizada (simulacao educativa)."""
        try:
            if HAS_BACKEND:
                try:
                    choice = route_compare(self.rota, optimized=self.otimizando)
                    self.lbl_bgp.configure(text=f"BGP/ISP:  {choice.bgp_path}   ~{choice.bgp_ping_est} ms")
                    self.lbl_overlay.configure(
                        text=f"Overlay:  {choice.overlay_path}   ~{choice.overlay_ping_est} ms   (−{choice.gain_ms} ms)"
                    )
                    self.lbl_bgp_as.configure(text="AS path: " + " → ".join(choice.bgp_as))
                    return
                except Exception as e:
                    print(f"[backend bgp] {e}")
            info = ROTAS.get(self.rota, {})
            bgp_path = info.get("bgp_path", "—")
            overlay = info.get("overlay_path", "—")
            bgp_ping = info.get("bgp_ping", info.get("base", 200))
            base = info.get("base", 175)
            # Se temos ping real, usa como base BGP aproximada
            with self._ping_lock:
                real = self.ping_real
            if real and real > 50:
                bgp_est = real + random.randint(5, 25)
            else:
                bgp_est = bgp_ping + random.randint(-8, 12)
            if self.otimizando:
                opt_est = max(70, int(base * random.uniform(0.55, 0.7)))
            else:
                opt_est = base
            ganho = max(0, bgp_est - opt_est)
            self.lbl_bgp.configure(
                text=f"BGP/ISP:  {bgp_path}   ~{bgp_est} ms"
            )
            self.lbl_overlay.configure(
                text=f"Overlay:  {overlay}   ~{opt_est} ms   (−{ganho} ms)"
            )
            ases = info.get("bgp_as", [])
            self.lbl_bgp_as.configure(
                text="AS path: " + " → ".join(ases) if ases else ""
            )
        except Exception as e:
            print(f"[bgp] {e}")

    def _update_smart_tip(self):
        """Avisos úteis com base no ping real e rota."""
        try:
            with self._ping_lock:
                real = self.ping_real
            tips = []
            # Recomendação de rota
            if self.rota == "Miami → São Paulo":
                tips.append("💡 Miami costuma ser pior de PT. Experimenta Madrid.")
            elif self.rota == "São Paulo (Direto)":
                tips.append("💡 Rota direta sem nós intermédios — Madrid costuma ser mais estável.")
            elif self.rota == "Madrid → São Paulo":
                tips.append("✅ Madrid é geralmente a melhor opção PT → BR.")

            if real > 0:
                if real > 220:
                    tips.append(f"⚠ Ping real alto ({real} ms). Rede instável ou horário de pico.")
                elif real > 180:
                    tips.append(f"📡 Ping real {real} ms — dentro do esperado PT→BR.")
                else:
                    tips.append(f"✨ Ping real bom ({real} ms) para PT→BR.")

            favs = self.cfg.get("favoritos", [])
            if favs and self.rota not in favs:
                tips.append(f"★ Favoritos: {', '.join(favs[:2])}")

            self.lbl_smart.configure(text="  |  ".join(tips) if tips else "")
        except Exception:
            pass

    # ---------- Admin Panel ----------
    def _open_admin(self):
        if self.role != "admin":
            return
        win = ctk.CTkToplevel(self)
        win.title(self.t["admin_panel"])
        win.geometry("560x640")
        win.configure(fg_color=COR_FUNDO)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Painel de Administração", font=ctk.CTkFont(size=16, weight="bold"), text_color=COR_TEXTO).pack(pady=(12, 8))

        # --- Criar utilizador ---
        uf = ctk.CTkFrame(win, fg_color=COR_CARD, corner_radius=8)
        uf.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(uf, text="➕  Criar conta de acesso", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_SEC).pack(anchor="w", padx=12, pady=(10, 6))

        row = ctk.CTkFrame(uf, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        eu = ctk.CTkEntry(row, placeholder_text="Nome de utilizador", width=160, height=30, fg_color="#21262d")
        eu.pack(side="left", padx=3)
        ep = ctk.CTkEntry(row, placeholder_text="Palavra-passe", show="•", width=160, height=30, fg_color="#21262d")
        ep.pack(side="left", padx=3)

        msg_u = ctk.CTkLabel(uf, text="A key de licença é gerada automaticamente", font=ctk.CTkFont(size=11), text_color=COR_SEC)
        msg_u.pack(pady=4)

        def create_u():
            res = self.auth.create_user(eu.get().strip(), ep.get())
            if res == "exists":
                msg_u.configure(text="❌ Esse utilizador já existe", text_color=COR_VERMELHO)
            elif res == "empty":
                msg_u.configure(text="❌ Preenche utilizador e palavra-passe", text_color=COR_VERMELHO)
            elif res == "key_used":
                msg_u.configure(text="❌ Chave já em uso", text_color=COR_VERMELHO)
            else:
                msg_u.configure(text=f"✅ Conta criada! Key: {res}", text_color=self.accent)
                eu.delete(0, "end")
                ep.delete(0, "end")
                refresh_users()
                refresh_lics()

        ctk.CTkButton(uf, text="Criar conta", width=180, height=32, fg_color=self.accent,
                      hover_color=self.hover, text_color="#0d1117", command=create_u).pack(pady=(2, 10))

        # --- Lista de utilizadores com histórico ---
        ctk.CTkLabel(win, text="👥  Contas e histórico de acesso", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_SEC).pack(anchor="w", padx=18, pady=(10, 4))
        user_box = ctk.CTkScrollableFrame(win, fg_color=COR_CARD, height=220)
        user_box.pack(fill="x", padx=14, pady=2)

        def refresh_users():
            for w in user_box.winfo_children():
                w.destroy()
            # Cabeçalho
            hdr = ctk.CTkFrame(user_box, fg_color="#21262d", corner_radius=4)
            hdr.pack(fill="x", pady=(0, 4), padx=2)
            for txt, w in [("Utilizador", 110), ("Criada em", 110), ("Último acesso", 110), ("", 70)]:
                ctk.CTkLabel(hdr, text=txt, font=ctk.CTkFont(size=10, weight="bold"), text_color=COR_SEC, width=w, anchor="w").pack(side="left", padx=4, pady=4)

            for u in self.auth.list_users():
                info = self.auth.data["users"][u]
                created = info.get("created_at") or "—"
                last = info.get("last_login") or "Nunca"
                role = info.get("role", "user")

                row = ctk.CTkFrame(user_box, fg_color="transparent")
                row.pack(fill="x", pady=2, padx=2)

                nome = f"{u}" + (" 👑" if role == "admin" else "")
                ctk.CTkLabel(row, text=nome, font=ctk.CTkFont(size=12), text_color=COR_TEXTO, width=110, anchor="w").pack(side="left", padx=4)
                ctk.CTkLabel(row, text=created, font=ctk.CTkFont(size=11), text_color=COR_SEC, width=110, anchor="w").pack(side="left", padx=4)
                ctk.CTkLabel(row, text=last, font=ctk.CTkFont(size=11), text_color=self.accent if last != "Nunca" else COR_SEC, width=110, anchor="w").pack(side="left", padx=4)

                if u != "admin":
                    def _del(name=u):
                        if self.auth.remove_user(name):
                            refresh_users()
                            refresh_lics()
                            msg_u.configure(text=f"Conta '{name}' removida", text_color=COR_LARANJA)
                    ctk.CTkButton(row, text="Excluir", width=70, height=24, fg_color=COR_VERMELHO,
                                  hover_color="#e84118", command=_del).pack(side="right", padx=4)
                else:
                    ctk.CTkLabel(row, text="—", width=70, text_color=COR_SEC).pack(side="right", padx=4)

        refresh_users()

        # --- Chaves de licença ---
        key_frame = ctk.CTkFrame(win, fg_color=COR_CARD, corner_radius=8)
        key_frame.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(key_frame, text="🔑  Chaves de licença", font=ctk.CTkFont(size=12, weight="bold"), text_color=COR_SEC).pack(anchor="w", padx=12, pady=(8, 4))
        self.admin_key_lbl = ctk.CTkLabel(key_frame, text="—", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.accent)
        self.admin_key_lbl.pack(pady=2)

        def gen():
            k = self.auth.generate_key()
            self.admin_key_lbl.configure(text=k)
            refresh_lics()

        ctk.CTkButton(key_frame, text="Gerar nova chave", width=180, height=30, fg_color="#21262d",
                      hover_color="#30363d", command=gen).pack(pady=(2, 8))

        lic_box = ctk.CTkScrollableFrame(win, fg_color=COR_CARD, height=90)
        lic_box.pack(fill="x", padx=14, pady=(0, 10))

        def refresh_lics():
            for w in lic_box.winfo_children():
                w.destroy()
            for k, v in list(self.auth.list_licenses().items())[-20:]:
                used = v.get("used_by") or "livre"
                active = "✓" if v.get("active") else "✗"
                created = v.get("created", "—")
                ctk.CTkLabel(
                    lic_box,
                    text=f"{active}  {k}  |  {used}  |  {created}",
                    font=ctk.CTkFont(size=11),
                    text_color=COR_TEXTO if v.get("active") else COR_SEC,
                    anchor="w"
                ).pack(fill="x", padx=8, pady=1)

        refresh_lics()

    def _logout(self):
        self.auth.clear_session()
        self._save_cfg()
        self.destroy()
        # Reinicia o fluxo de login
        main()

    # ---------- resto da lógica (igual versões anteriores, resumido) ----------
    def _on_game(self, name):
        self.jogo = name
        self._atualizar_icone_jogo(name)
        self._atualizar_banner(name)
        self._aplicar_cor_jogo(name)
        p = self.cfg.get("perfis", {}).get(name)
        if p and p in ROTAS:
            self.rota = p
            self.combo_rota.set(p)
            self._rebuild_route_map()
            self._update_fav_btn()
        self._update_smart_tip()
        self._save_cfg()

    def _on_route(self, name):
        self.rota = name
        self._rebuild_route_map()
        self._update_fav_btn()
        self._update_smart_tip()
        self._update_bgp_panel()
        self.cfg.setdefault("perfis", {})[self.jogo] = name
        self._save_cfg()

    def _toggle(self):
        if self.conectando:
            return
        if self.otimizando:
            self._stop()
        else:
            self._start_anim()

    def _start_anim(self):
        self.conectando = True
        self.ping_antes = self.ping_atual or ROTAS[self.rota]["base"]
        self.btn_opt.configure(state="disabled")
        self.progress.pack(fill="x", pady=2)
        self.lbl_conn.pack()
        self.lbl_status.configure(text=self.t["connecting"], text_color=self.accent)
        steps = [(self.t["c1"], 0.25), (self.t["c2"], 0.5), (self.t["c3"], 0.75), (self.t["c4"], 1.0)]

        def go(i=0):
            if i >= len(steps):
                self.conectando = False
                self.otimizando = True
                self.inicio = datetime.now()
                if HAS_BACKEND:
                    try:
                        start_optimization(self.rota, competitive=self.cfg.get("competitivo", False))
                    except Exception as e:
                        print(f"[backend start] {e}")
                self.progress.pack_forget()
                self.lbl_conn.pack_forget()
                self.btn_opt.configure(state="normal", text=self.t["stop"], fg_color=COR_VERMELHO, hover_color="#e84118")
                self.lbl_status.configure(text=self.t["on"], text_color=self.accent)
                self.lbl_before.configure(text=f"{self.t['before']}: {self.ping_antes} ms")
                self._beep()
                self._animate_route_map(0)
                self._update_smart_tip()
                self._update_bgp_panel()
                return
            self.lbl_conn.configure(text=steps[i][0])
            self.progress.set(steps[i][1])
            # Ilumina nós durante a conexão
            try:
                for j, lbl in enumerate(self.hop_labels):
                    lbl.configure(fg_color=self.accent if j <= i else "#21262d",
                                  text_color="#0d1117" if j <= i else COR_SEC)
            except Exception:
                pass
            self.after(600, lambda: go(i + 1))
        go()

    def _stop(self):
        if HAS_BACKEND:
            try:
                stop_optimization(game=getattr(self, "jogo", ""), user=getattr(self, "username", ""))
            except Exception as e:
                print(f"[backend stop] {e}")
        if self.inicio:
            dur = int((datetime.now() - self.inicio).total_seconds())
            self.cfg["tempo_total_seg"] = self.cfg.get("tempo_total_seg", 0) + dur
            self.historico.append({
                "data": datetime.now().strftime("%d/%m %H:%M"), "jogo": self.jogo, "rota": self.rota,
                "antes": self.ping_antes, "depois": self.ping_atual,
                "duracao": f"{dur // 60:02d}:{dur % 60:02d}", "user": self.username,
            })
            save_json(HISTORY_FILE, self.historico[-30:])
            self._save_cfg()
            self.lbl_total.configure(text=f"{self.t['total']}: {self._fmt_total()}")
        self.otimizando = False
        self.btn_opt.configure(text=self.t["start"], fg_color=self.accent, hover_color=self.hover)
        self.lbl_status.configure(text=self.t["off"], text_color=COR_VERMELHO)
        self.lbl_session.configure(text=f"{self.t['session']}: --")
        self.lbl_after.configure(text=f"{self.t['after']}: --")
        self.lbl_alert.configure(text="")
        self._beep()

    def _test(self):
        self.btn_test.configure(state="disabled")

        def done():
            p = self._measure_ping()
            self.lbl_info.configure(text=f"Ping real: {p} ms" if p else "Falha no teste")
            self.btn_test.configure(state="normal")
        threading.Thread(target=lambda: (time.sleep(0.2), self.after(0, done)), daemon=True).start()

    def _toggle_overlay(self):
        if self.overlay_win and self.overlay_win.winfo_exists():
            self.overlay_win.destroy()
            self.overlay_win = None
            return
        ov = ctk.CTkToplevel(self)
        self.overlay_win = ov
        ov.geometry("180x80")
        ov.configure(fg_color=COR_FUNDO)
        ov.attributes("-topmost", True)
        ov.resizable(False, False)
        self.ov_ping = ctk.CTkLabel(ov, text="-- ms", font=ctk.CTkFont(size=24, weight="bold"), text_color=self.accent)
        self.ov_ping.pack(pady=(10, 0))
        self.ov_st = ctk.CTkLabel(ov, text=self.t["off"], font=ctk.CTkFont(size=10), text_color=COR_SEC)
        self.ov_st.pack()

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title(self.t["settings"])
        win.geometry("380x420")
        win.configure(fg_color=COR_FUNDO)
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text=self.t["settings"], font=ctk.CTkFont(size=15, weight="bold"), text_color=COR_TEXTO).pack(pady=10)
        box = ctk.CTkFrame(win, fg_color=COR_CARD, corner_radius=8)
        box.pack(fill="x", padx=14)
        switches = {}
        for key, label in [("bandeja", self.t["tray"]), ("som", self.t["sound"]), ("competitivo", self.t["comp"]),
                           ("grafico", self.t["graph"]), ("always_on_top", self.t["aot"])]:
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(r, text=label, font=ctk.CTkFont(size=12), text_color=COR_TEXTO).pack(side="left")
            sw = ctk.CTkSwitch(r, text="", width=42, progress_color=self.accent)
            if self.cfg.get(key):
                sw.select()
            sw.pack(side="right")
            switches[key] = sw

        def salvar():
            for k, sw in switches.items():
                self.cfg[k] = sw.get() == 1
            self.attributes("-topmost", self.cfg["always_on_top"])
            self._save_cfg()
            if self.cfg.get("grafico") and HAS_GRAPH and not self.graph_frame.winfo_ismapped():
                self.graph_frame.pack(fill="x", pady=(6, 0), before=self.btn_opt)
            elif not self.cfg.get("grafico"):
                self.graph_frame.pack_forget()
            win.destroy()
        ctk.CTkButton(win, text=self.t["save"], width=120, height=32, fg_color=self.accent,
                      hover_color=self.hover, text_color="#0d1117", command=salvar).pack(pady=14)

    def _open_history(self):
        win = ctk.CTkToplevel(self)
        win.title(self.t["history"])
        win.geometry("460x320")
        win.configure(fg_color=COR_FUNDO)
        fr = ctk.CTkScrollableFrame(win, fg_color=COR_CARD)
        fr.pack(fill="both", expand=True, padx=12, pady=12)
        for h in reversed(self.historico[-20:]):
            t = f"{h.get('data','')} | {h.get('user','')} | {h.get('antes','?')}→{h.get('depois','?')}ms | {h.get('duracao','')}"
            ctk.CTkLabel(fr, text=t, font=ctk.CTkFont(size=11), text_color=COR_TEXTO, anchor="w").pack(fill="x", padx=6, pady=1)

    def _on_close(self):
        self._save_cfg()
        if self.cfg.get("bandeja") and HAS_TRAY:
            self.withdraw()
            if not self.tray_icon:
                def show(i, item):
                    self.after(0, self._restore)
                def quit_(i, item):
                    self.after(0, self._quit)
                img = carregar_icone_pil("optilag", 64)
                if img is None:
                    img = Image.new("RGB", (64, 64), (5, 12, 20))
                    ImageDraw.Draw(img).ellipse([10, 10, 54, 54], fill=(0, 240, 255))
                else:
                    img = img.convert("RGB")
                menu = pystray.Menu(pystray.MenuItem("Show", show, default=True), pystray.MenuItem("Quit", quit_))
                self.tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
                threading.Thread(target=self.tray_icon.run, daemon=True).start()
        else:
            self._quit()

    def _restore(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.deiconify()

    def _quit(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
        sys.exit(0)

    def _beep(self):
        if self.cfg.get("som") and HAS_SOUND:
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def _start_loops(self):
        threading.Thread(target=self._metrics_loop, daemon=True).start()
        threading.Thread(target=self._real_ping_loop, daemon=True).start()
        if HAS_PSUTIL:
            threading.Thread(target=self._detect_loop, daemon=True).start()

    def _real_ping_loop(self):
        while True:
            try:
                if not self.winfo_exists():
                    break
            except Exception:
                break
            p = self._measure_ping()
            if p is not None:
                with self._ping_lock:
                    self.ping_real = p
                    self.graph_data_real.append(p)
                    if len(self.graph_data_real) > 40:
                        self.graph_data_real.pop(0)
            time.sleep(5)

    def _detect_loop(self):
        while True:
            try:
                if not self.winfo_exists():
                    break
                names = {p.name() for p in psutil.process_iter(["name"])}
                found = None
                for jogo, info in JOGOS.items():
                    if any(proc in names for proc in info["processos"]):
                        found = jogo
                        break
                txt = f"🟢 {self.t['detect']}: {found}" if found else self.t["no_game"]

                def _safe_set(t=txt, jogo=found):
                    try:
                        if self.winfo_exists():
                            self.lbl_detect.configure(text=t)
                            if jogo and jogo != self.jogo:
                                self.combo_jogo.set(jogo)
                                self._on_game(jogo)
                    except Exception:
                        pass
                self.after(0, _safe_set)
            except Exception:
                pass
            time.sleep(4)

    def _metrics_loop(self):
        while True:
            try:
                # Para se a janela principal já não existir
                if not self.winfo_exists():
                    break
                info = ROTAS[self.rota]
                base = info["base"] + JOGOS.get(self.jogo, {}).get("extra", 0)
                var = info["var"]
                if self.otimizando:
                    fator = random.uniform(0.48, 0.60) if self.cfg.get("competitivo") else random.uniform(0.58, 0.72)
                    with self._ping_lock:
                        real = self.ping_real
                    base_ref = min(base, real + 40) if real > 0 else base
                    self.ping_atual = max(70, int(base_ref * fator + random.uniform(-var * 0.2, var * 0.2)))
                    self.loss = round(random.uniform(0, 0.4), 1)
                else:
                    with self._ping_lock:
                        real = self.ping_real
                    self.ping_atual = (real + random.randint(-5, 12)) if real > 0 else int(base + random.uniform(-var * 0.3, var))
                    self.ping_atual = max(70, self.ping_atual)
                    self.loss = round(random.uniform(0.8, 3.5), 1)
                self.graph_data.append(self.ping_atual)
                if len(self.graph_data) > 40:
                    self.graph_data.pop(0)
                try:
                    self.after(0, self._update_ui)
                except Exception:
                    break
            except Exception:
                pass
            time.sleep(1)

    def _update_ui(self):
        try:
            if not self.winfo_exists():
                return
            cor = self.accent if self.otimizando else COR_LARANJA
            self.lbl_ping.configure(text=f"{self.ping_atual} ms", text_color=cor)
            # Qualidade
            try:
                qtxt, qcor = self._qualidade_ping(self.ping_atual)
                self.lbl_quality.configure(text=f"● Qualidade: {qtxt}", text_color=qcor)
            except Exception:
                pass
            with self._ping_lock:
                real = self.ping_real
            probe = getattr(self, "_last_probe", None)
            detail = getattr(self, "_probe_detail", {}) or {}
            if real:
                parts = []
                if detail.get("udp"):
                    parts.append(f"U{detail['udp']}")
                if detail.get("tcp"):
                    parts.append(f"T{detail['tcp']}")
                extra = (" " + "/".join(parts)) if parts else (f" {probe}" if probe else "")
                self.lbl_real.configure(text=f"{real} ms{extra}", text_color=COR_SEC)
            else:
                self.lbl_real.configure(text="--", text_color=COR_SEC)
            self.lbl_loss.configure(text=f"{self.loss} %", text_color=cor)
            if self.otimizando and self.ping_antes:
                gain = max(0, min(55, int((1 - self.ping_atual / max(self.ping_antes, 1)) * 100)))
                self.lbl_gain.configure(text=f"{gain} %", text_color=self.accent)
                self.lbl_after.configure(text=f"{self.t['after']}: {self.ping_atual} ms")
                self.lbl_alert.configure(text=self.t["high"] if self.ping_atual > 170 else "")
            else:
                self.lbl_gain.configure(text="--", text_color=COR_SEC)
            if self.otimizando and self.inicio:
                d = datetime.now() - self.inicio
                m, s = divmod(int(d.total_seconds()), 60)
                self.lbl_session.configure(text=f"{self.t['session']}: {m:02d}:{s:02d}")
            if self.overlay_win is not None:
                try:
                    if self.overlay_win.winfo_exists():
                        self.ov_ping.configure(text=f"{self.ping_atual} ms", text_color=cor)
                        self.ov_st.configure(text=self.t["on"] if self.otimizando else self.t["off"])
                except Exception:
                    self.overlay_win = None
            if self.cfg.get("grafico") and HAS_GRAPH and self.graph_data:
                try:
                    self.line.set_data(range(len(self.graph_data)), self.graph_data)
                    if getattr(self, "graph_data_real", None):
                        xs = list(range(len(self.graph_data_real)))
                        self.line_real.set_data(xs, list(self.graph_data_real))
                    ys = list(self.graph_data) + list(getattr(self, "graph_data_real", []) or [0])
                    self.ax.set_xlim(0, max(40, len(self.graph_data)))
                    self.ax.set_ylim(0, max(ys) + 40)
                    self.canvas.draw_idle()
                except Exception:
                    pass
            # Atualiza dica inteligente a cada ~5 segundos de UI
            if not hasattr(self, "_tip_counter"):
                self._tip_counter = 0
            self._tip_counter += 1
            if self._tip_counter % 5 == 0:
                self._update_smart_tip()
                self._update_bgp_panel()
        except Exception:
            # Widget destruído (logout, fechar janela, etc.) — ignora
            pass


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    auth = AuthManager()

    # Setup inicial
    if not auth.setup_done():
        setup = SetupWindow(auth)
        setup.mainloop()
        if not auth.setup_done():
            return
        # Mostra a key do admin
        admin_key = auth.data["users"]["admin"]["license"]
        print(f"Admin criado. Licença admin: {admin_key}")

    # Sessão lembrada?
    user = auth.get_session()
    role = None
    if user:
        role = auth.data["users"][user].get("role", "user")
        # Atualiza último acesso mesmo com sessão lembrada
        auth.data["users"][user]["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if not auth.data["users"][user].get("created_at"):
            auth.data["users"][user]["created_at"] = auth.data["users"][user]["last_login"]
        auth.save()
    else:
        login = LoginWindow(auth)
        login.mainloop()
        user = login.result_user
        role = login.result_role
        if not user:
            return

    app = OptiLagApp(auth, user, role)
    app.mainloop()


if __name__ == "__main__":
    main()

# OptiLag

Otimizador de latência estilo **ExitLag** para jogar servidores BR a partir de Portugal.

> Simulação de rotas overlay + **sondas reais** UDP/TCP.  
> Não altera o BGP da operadora nem redireciona o tráfego do jogo a nível de sistema.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![UI](https://img.shields.io/badge/UI-CustomTkinter-green)
![API](https://img.shields.io/badge/API-FastAPI-teal)
![Version](https://img.shields.io/badge/version-2.1.0-orange)

---

## Funcionalidades

| Área | Detalhe |
|------|---------|
| **UI** | Tema cyberpunk, banner, ícones por jogo, cores dinâmicas |
| **Jogos** | PUBG, Valorant, CS2, Fortnite, LoL, Apex, Warzone, Roblox |
| **Rede** | Multi-probe **UDP** (DNS) + **TCP** (443) + fallback ICMP |
| **Rotas** | BGP (ISP) vs Overlay · Dijkstra no backend |
| **Contas** | Login, admin, licenças locais |
| **API** | FastAPI em `127.0.0.1:8765` · Pydantic v2 |
| **Dados** | SQLite (probes + sessões) |

---

## Estrutura

```text
OptiLag/
├── optilag_pubg.py          # Interface desktop
├── optilag_backend/
│   ├── network/             # Probes UDP/TCP/ICMP + sampler
│   ├── routing/             # Grafo + Dijkstra + BGP sim
│   ├── core/                # Motor de sessão
│   ├── models.py            # Pydantic (validação/serialização)
│   ├── api.py               # FastAPI
│   ├── bridge.py            # Ponte UI ↔ backend
│   ├── persistence.py       # SQLite
│   └── learn_pydantic.py    # Demo Pydantic
├── icons/                   # Ícones SVG/PNG
├── requirements.txt
└── README.md
```

---

## Instalação

```bash
git clone https://github.com/mathenrique75/OptiLag.git
cd OptiLag
pip install -r requirements.txt
```

**Dependências principais:** `customtkinter`, `pillow`, `fastapi`, `uvicorn`, `pydantic`, `pystray`, `psutil`, `matplotlib`

---

## Como correr

### App (interface)

```bash
python optilag_pubg.py
```

### API local (outro terminal)

```bash
python -m optilag_backend.api
```

- Docs: http://127.0.0.1:8765/docs  
- Health: http://127.0.0.1:8765/health  
- Probe: http://127.0.0.1:8765/probe  

### Testes backend

```bash
python -m optilag_backend.cli_test
python -m optilag_backend.learn_pydantic
```

---

## API (resumo)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/probe` | Sonda UDP+TCP agora |
| GET | `/probe/history` | Histórico |
| GET | `/routes` | Lista de rotas |
| GET | `/routes/{nome}/compare` | BGP vs Overlay |
| GET/POST | `/engine` | Estado / start·stop·tick |
| GET | `/stats` | Contagens e média |
| GET | `/sessions` | Sessões guardadas |

---

## Git

```bash
git status
git add .
git commit -m "Mensagem clara do que mudou"
git push
```

**Não versionar:** `*.db`, `optilag_auth.json`, configs locais (ver `.gitignore`).

---

## Aviso

O OptiLag é um projeto **educativo / de simulação**.  
As rotas “otimizadas” e o painel BGP vs Overlay **não** modificam o encaminhamento real dos pacotes do jogo no Windows.

---

## Autor

[mathenrique75](https://github.com/mathenrique75) · v2.1.0

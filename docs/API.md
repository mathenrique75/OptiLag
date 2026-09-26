# OptiLag API

Base: http://127.0.0.1:8765
Swagger: http://127.0.0.1:8765/docs

## Endpoints

| Method | Path | Descricao |
|--------|------|----------|
| GET | / | Meta |
| GET | /health | Health |
| POST | /auth/login | JWT login |
| GET | /auth/me | Token info |
| GET | /probe | Probe agora |
| GET | /probe/history | Historico |
| GET | /routes | Lista rotas |
| GET | /routes/best | Melhor overlay |
| GET | /routes/{name} | Comparar rota |
| GET | /engine | Estado motor |
| POST | /engine | start/stop/tick |
| GET | /sessions | Sessoes |
| GET | /stats | Stats |
| POST | /export | Export JSON |

Auth: Authorization: Bearer <token>
Env: OPTILAG_JWT_REQUIRED, OPTILAG_JWT_SECRET

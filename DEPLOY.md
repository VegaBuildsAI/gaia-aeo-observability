# Deploy a Railway — Gaia AEO Observability Engine

Cuenta de Railway: **`msvv11@gmail.com`**

El deploy requiere login interactivo (OAuth) y cargar la `ANTHROPIC_API_KEY` como
secreto — pasos que corre el usuario. Todo lo demás ya está listo en el repo.

## 0. Requisitos
- Node instalado (para la CLI) o usar la UI web de Railway.
- Instalar la CLI: `npm i -g @railway/cli`

## 1. Login (interactivo)
```bash
railway login          # abre el navegador → entrar con msvv11@gmail.com
```

## 2. Crear el proyecto
Desde la carpeta `aeo-observability/`:
```bash
railway init           # crea un proyecto nuevo (o 'railway link' a uno existente)
```

## 3. Agregar Postgres (persistencia de 2 meses)
```bash
railway add            # elegir "PostgreSQL"
```
Railway inyecta `DATABASE_URL` automáticamente al servicio. El código ya normaliza
`postgres://` → `postgresql://` (ver app/config.py).

## 4. Cargar variables / secretos
```bash
railway variables --set "ANTHROPIC_API_KEY=sk-ant-..." \
                  --set "ADMIN_TOKEN=un-token-secreto" \
                  --set "CLAUDE_MODEL=claude-opus-4-8" \
                  --set "PROBE_CRON=0 9 * * *" \
                  --set "CAMPAIGN_DAYS=60"
```
(`.env.example` lista todas las variables disponibles.)

## 5. Deploy
```bash
railway up             # build por Dockerfile + arranque de uvicorn
```
Railway detecta `railway.json` (builder Dockerfile + healthcheck en `/api/status`).

## 6. Exponer el dominio
```bash
railway domain         # genera una URL pública https://<proyecto>.up.railway.app
```

## 7. Verificar
- Abrir la URL → carga el dashboard.
- `GET /api/status` → `"ok": true`, `engines_available.claude: true`.
- Dashboard → botón **▶ Correr sondeo ahora** (pide el `ADMIN_TOKEN`) → la consola
  muestra el sondeo corriendo y las tablas se llenan.
- El scheduler correrá solo 1×/día según `PROBE_CRON` durante los 2 meses.

## Notas
- **Costo de tokens:** cadencia moderada = ~18 prompts × 1/día × ~60 días ≈ 1080
  llamadas con web_search a lo largo de la campaña. Ajustable con `PROBE_CRON` y la
  batería en `app/prompts.py`.
- **Otros motores:** al setear `OPENAI_API_KEY` / `PERPLEXITY_API_KEY` / `GEMINI_API_KEY`
  y completar sus adapters (`app/engines/*.py`), esos motores entran al sondeo solos.
- **Zona horaria del cron:** el scheduler corre en UTC.

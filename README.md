# Gaia School — Motor de Observabilidad AEO

Recolecta datos **en vivo durante 2 meses** para responder: *¿los motores de IA
citan a Gaia School cuando un padre pregunta por escuelas Waldorf/bilingües en la
Península de Nicoya?* — y monitorea en vivo lo que las IA "ven" sobre Gaia vs. sus
competidores. Es el diferenciador AEO de AXIO: pasa de "hicimos cambios" a
"aquí está la curva de resultados en vivo, auditada".

Espeja el motor de observabilidad de **JPS Tiempos Architect** (dashboard + API JSON
+ estadística propia sin dependencias pesadas) y monta encima un **chatbot** con el
mismo tratamiento visual que JPS Tiempos Lab.

## Cómo funciona
1. **Sondeo (`app/probe.py`)** — corre una batería de ~18 prompts (marca/no-marca,
   ES/EN, long-tail, comparativos) contra los motores activos.
2. **Motor Claude (`app/engines/claude.py`)** — usa la herramienta nativa `web_search`:
   Claude busca en vivo y responde con citaciones. Es a la vez un motor real que
   medimos y un telescopio de la web accesible-a-IA. Otros motores = adapters
   pluggables (se activan con su API key).
3. **Extracción (`app/matching.py`)** — detecta mención de Gaia, presencia en las
   fuentes citadas + ranking, competidores y sentimiento.
4. **Analítica (`app/analytics.py`)** — citation rate con CI de Wilson, share of voice,
   tendencia, efectividad por prompt, ranking de dominios, anomalías.
5. **Dashboard (`static/index.html`)** — consola en vivo, gráficas de tendencia y
   share of voice, tablas por motor/clase/dominio/prompt.
6. **Chatbot (`app/chat.py`)** — "Gaia AEO Assistant": Claude con tools que leen la
   DB y responde solo con datos reales (SSE streaming).
7. **Sondeo manual** — no hay scheduler automático por defecto: los probes solo
   corren cuando los disparás (botón ▶ o `POST /api/probe/run`), para controlar el
   gasto del token. (`SCHEDULER_ENABLED=true` reactiva el tick diario si algún día lo querés.)
8. **Historial por corrida** — cada disparo recibe un `run_id` y conserva una fila
   inmutable por prompt/motor en `probe_run_result`. La tabla `probe_result` sigue
   siendo la vista diaria deduplicada que alimenta el dashboard.

## Correr en local

### Opción A — Docker Compose (con Postgres)
```bash
cp .env.example .env      # y poné tu ANTHROPIC_API_KEY + ADMIN_TOKEN
docker compose up --build
# → http://localhost:8000
```

### Opción B — Python directo (SQLite)
```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # o setear en .env
uvicorn app.main:app --reload
# → http://localhost:8000
```

## Uso
- Abrí el dashboard → **▶ Correr sondeo ahora** (pide el `ADMIN_TOKEN`).
- La consola muestra el progreso; las tablas y gráficas se llenan al terminar.
- El chatbot (💬, abajo a la derecha) responde sobre los datos en vivo.

## Tests
```bash
pip install pytest
pytest -q
```

## Deploy
Ver [DEPLOY.md](DEPLOY.md) — Railway (cuenta `msvv11@gmail.com`).

## API
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/api/status` | Estado general + motores disponibles |
| GET | `/api/state` | Estado del sondeo + log de consola |
| GET | `/api/metrics?since=YYYY-MM-DD` | Reporte analítico completo |
| GET | `/api/probes?since=&limit=` | Filas de sondeo crudas |
| GET | `/api/runs?since=&limit=` | Historial de corridas por fecha y `run_id` |
| GET | `/api/run-results?run_id=&since=&limit=` | Resultados inmutables de cada corrida |
| POST | `/api/probe/run` | Dispara sondeo manual y devuelve `run_id` (header `X-Admin-Token`) |
| POST | `/api/chat` | Chatbot (SSE) — body `{messages:[...]}` |

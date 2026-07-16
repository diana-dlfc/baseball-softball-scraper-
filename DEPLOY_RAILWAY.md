# Deploy a Railway (vía CLI)

Deploy directo desde esta carpeta con `railway up` — sin GitHub de por
medio (evita el problema de "Railway no muestra el repo" del proyecto
anterior).

## Lecciones del proyecto anterior ya integradas en el código

- Flags obligatorios de Chromium en Docker (`--no-sandbox`,
  `--disable-dev-shm-usage`, etc.) → `playwright_manager.py`
- Reinicio preventivo del navegador cada N negocios → `scrape_pipeline.py`
- Timeout duro por negocio (nada se cuelga indefinidamente) → 120s
- `credentials.json` reconstruido desde variable de entorno → `helpers.py`
- `startCommand` explícito → `railway.json`
- Concurrencia configurable por env (empezar con 1 en Railway)
- Imagen Docker oficial de Playwright (Chromium preinstalado)

## Paso 1 — Instalar la CLI y autenticarse

```powershell
npm install -g @railway/cli
railway login
```

## Paso 2 — Crear el proyecto (desde esta carpeta)

```powershell
cd C:\baseball-softball-scraper
railway init
```

Elige un nombre (ej. `baseball-softball-scraper`).

## Paso 3 — Configurar variables de entorno

Copia los valores desde tu `.env` local:

```powershell
railway variables --set "SUPABASE_URL=..." `
  --set "SUPABASE_KEY=..." `
  --set "GOOGLE_PLACES_API_KEY=..." `
  --set "SEARCH_ENGINE=auto" `
  --set "LLM_API_KEY=..." `
  --set "LLM_BASE_URL=https://api.cerebras.ai/v1" `
  --set "LLM_MODEL=gpt-oss-120b" `
  --set "LLM_FALLBACK_API_KEY=..." `
  --set "LLM_FALLBACK_BASE_URL=https://integrate.api.nvidia.com/v1" `
  --set "LLM_FALLBACK_MODEL=deepseek-ai/deepseek-v4-flash" `
  --set "LLM_FALLBACK2_API_KEY=..." `
  --set "LLM_FALLBACK2_BASE_URL=https://api.groq.com/openai/v1" `
  --set "LLM_FALLBACK2_MODEL=llama-3.1-8b-instant" `
  --set "LLM_FALLBACK3_API_KEY=..." `
  --set "LLM_FALLBACK3_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/" `
  --set "LLM_FALLBACK3_MODEL=gemini-2.5-flash-lite" `
  --set "GOOGLE_SHEETS_ID=..." `
  --set "GOOGLE_SERVICE_ACCOUNT_FILE=credentials/credentials.json" `
  --set "MAX_CONCURRENT_PAGES=1" `
  --set "BROWSER_RESTART_AFTER=200" `
  --set "RUN_SEARCH=false" `
  --set "RUN_SCRAPE=true" `
  --set "RUN_CLASSIFY=true" `
  --set "RUN_SYNC=true"
```

**La credencial de Google Sheets** (el JSON no va en el repo — se pasa
completo como variable):

```powershell
$json = Get-Content credentials\credentials.json -Raw
railway variables --set "GOOGLE_SHEETS_CREDENTIALS_JSON=$json"
```

> Si PowerShell da problemas con las comillas del JSON, pégala a mano en
> Railway → tu servicio → Variables → New Variable.

## Paso 4 — Deploy

```powershell
railway up
```

Construye la imagen (la primera vez tarda ~5 min por Playwright) y
arranca `python -m app.orchestrator`.

## Paso 5 — Monitorear

```powershell
railway logs
```

Deberías ver el banner del orquestador y las fases ejecutándose.

## Notas de operación

- **Fases**: controladas por `RUN_SEARCH/RUN_SCRAPE/RUN_CLASSIFY/RUN_SYNC`.
  La cosecha de Google (`RUN_SEARCH`) está apagada por defecto porque ya
  se corrió; enciéndela solo para re-cosechar.
- **El contenedor termina al completar** todas las fases. Para corridas
  recurrentes (ej. re-cosechar y re-enriquecer cada semana), configura un
  cron en Railway: servicio → Settings → Cron Schedule (ej. `0 6 * * 1`).
- **Resume**: si el contenedor muere a mitad de una fase, Railway lo
  reinicia (hasta 3 veces) y cada fase continúa donde quedó gracias a
  las columnas de estado en Supabase. El checkpoint de búsquedas
  (`output/checkpoint.json`) es efímero en Railway — para re-cosechas
  completas no importa (el dedup evita duplicados).
- **Concurrencia**: `MAX_CONCURRENT_PAGES=1` al inicio. Si tras unas
  horas los logs se ven estables, puedes subir a 2-3.

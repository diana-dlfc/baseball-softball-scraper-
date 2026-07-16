# Imagen oficial de Playwright para Python: trae Chromium y todas sus
# dependencias de sistema ya instaladas (evita el 90% de los problemas
# de Playwright en Railway/Docker).
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY . .

# Los logs van a stdout/stderr; Railway los captura automáticamente
CMD ["python", "-m", "app.orchestrator"]

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

# Executa a aplicação sem privilégios de root
RUN useradd --create-home --uid 1000 appuser

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts

USER appuser

EXPOSE 8000

# --proxy-headers: respeita o HTTPS informado pelo proxy do Render
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]

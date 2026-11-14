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
COPY --chown=appuser:appuser migracoes ./migracoes
COPY --chown=appuser:appuser alembic.ini ./

USER appuser

EXPOSE 8000

# Aplica as migrações pendentes (Alembic) antes de subir a API; se falharem,
# o contêiner não inicia e o Render mantém a versão anterior no ar.
# --proxy-headers: respeita o HTTPS informado pelo proxy do Render
CMD ["sh", "-c", "python -m scripts.criar_tabelas && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]

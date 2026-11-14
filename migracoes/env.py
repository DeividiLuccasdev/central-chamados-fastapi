"""Ambiente do Alembic: usa o mesmo banco e os mesmos modelos da aplicação."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

from app import models  # noqa: F401  (registra os modelos no Base)
from app.core.config import settings
from app.database import Base

config = context.config

# Quem chama pela API (scripts e testes) pode passar a URL e desligar os logs
if config.config_file_name and config.attributes.get("configurar_logs", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def url_banco() -> str:
    url = config.attributes.get("url") or settings.url_banco

    if isinstance(url, URL):
        return url.render_as_string(hide_password=False)

    return url


def rodar_offline() -> None:
    context.configure(
        url=url_banco(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    engine = create_engine(url_banco(), poolclass=pool.NullPool)

    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()

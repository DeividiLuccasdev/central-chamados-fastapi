"""Cria ou atualiza as tabelas do banco configurado aplicando as migrações (Alembic).

Uso: python -m scripts.criar_tabelas

Bancos criados antes do Alembic (pelo antigo create_all) já têm a estrutura da
revisão inicial: nesse caso ela é só marcada como aplicada (stamp) e as
migrações seguintes rodam normalmente.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from app.core.config import settings

RAIZ = Path(__file__).resolve().parent.parent
REVISAO_INICIAL = "0001"


def configuracao(url: str | URL | None = None) -> Config:
    config = Config(str(RAIZ / "alembic.ini"))
    config.attributes["configurar_logs"] = False

    if url is not None:
        config.attributes["url"] = url

    return config


def migrar(url: str | URL | None = None) -> None:
    engine = create_engine(url or settings.url_banco)

    try:
        tabelas = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    config = configuracao(url)

    if "usuarios" in tabelas and "alembic_version" not in tabelas:
        command.stamp(config, REVISAO_INICIAL)

    command.upgrade(config, "head")


if __name__ == "__main__":
    migrar()
    print("Tabelas criadas/atualizadas com sucesso!")

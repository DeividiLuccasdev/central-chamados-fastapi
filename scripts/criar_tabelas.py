"""Cria as tabelas no banco configurado.

Uso: python -m scripts.criar_tabelas
"""

from app import models  # noqa: F401  (registra os modelos no Base)
from app.database import Base, engine

Base.metadata.create_all(bind=engine)

print("Tabelas criadas com sucesso!")

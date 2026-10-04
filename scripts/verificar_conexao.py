"""Verifica a conexão com o banco configurado.

Uso: python -m scripts.verificar_conexao
"""

from sqlalchemy import text

from app.database import engine

with engine.connect() as conexao:
    resultado = conexao.execute(
        text("SELECT current_database();")
    )

    print("Banco conectado:", resultado.scalar())

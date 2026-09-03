from sqlalchemy import text
from database import engine


with engine.connect() as conexao:
    resultado = conexao.execute(
        text("SELECT current_database();")
    )

    print("Banco conectado:", resultado.scalar())
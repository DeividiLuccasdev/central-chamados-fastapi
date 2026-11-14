"""Cria ou restaura o login público de demonstração.

Uso: python -m scripts.criar_usuario_demo

Roda no início do contêiner, logo depois das migrações, mas só faz algo no
Render (RENDER=true) ou com CRIAR_USUARIO_DEMO=true: bancos locais e de teste
não ganham o usuário. Se a conta já existir, ela é reativada e a senha volta
ao valor publicado no README, então uma demo alterada se recupera a cada deploy.
"""

import sys

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import services
from app.core.config import Settings
from app.database import SessionLocal
from scripts.criar_usuario import criar_ou_redefinir

EMAIL_DEMO = services.EMAIL_DEMO
SENHA_DEMO = "Demo@2026"
NOME_DEMO = "Usuário Demo"


def garantir_usuario_demo(db: Session) -> bool:
    """Cria (True) ou restaura (False) o usuário de demonstração.

    É seguro com dois contêineres subindo juntos: o índice único em lower(email)
    faz o segundo insert falhar e ele só redefine a conta que o primeiro criou.
    """

    return criar_ou_redefinir(db, EMAIL_DEMO, NOME_DEMO, SENHA_DEMO)


def main(config: Settings | None = None) -> None:
    config = config or Settings()

    if not config.usuario_demo_habilitado:
        print("Usuário de demonstração ignorado (defina CRIAR_USUARIO_DEMO=true para criar).")
        return

    try:
        with SessionLocal() as db:
            criado = garantir_usuario_demo(db)
    except SQLAlchemyError as erro:
        # A demo não deve impedir a API de subir: as migrações já passaram
        print(f"Não foi possível preparar o usuário de demonstração: {erro}", file=sys.stderr)
        return

    acao = "criado" if criado else "restaurado"
    print(f"Usuário de demonstração {EMAIL_DEMO} {acao}.")


if __name__ == "__main__":
    main()

"""Cria um usuário ou redefine a senha de um usuário existente.

Útil para criar o primeiro acesso ou recuperar uma senha esquecida,
já que pelo sistema só um usuário logado pode cadastrar outros.

Uso:
    python -m scripts.criar_usuario --email voce@exemplo.com --nome "Seu Nome"

A senha é pedida no terminal (não fica no histórico). Se o e-mail já existir,
a senha é redefinida e o usuário é reativado.
"""

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app import models, services
from app.core.security import gerar_hash_senha
from app.database import SessionLocal

TAMANHO_MINIMO_SENHA = 6


def _redefinir(db: Session, usuario: models.Usuario, nome: str | None, senha_hash: str) -> None:
    usuario.senha = senha_hash
    usuario.ativo = True

    if nome:
        usuario.nome = nome

    db.commit()


def criar_ou_redefinir(db: Session, email: str, nome: str | None, senha: str) -> bool:
    """Retorna True se criou um usuário novo e False se redefiniu um existente."""

    email = models.normalizar_email(email)
    senha_hash = gerar_hash_senha(senha)

    usuario = services.buscar_usuario_por_email(db, email)

    if usuario:
        _redefinir(db, usuario, nome, senha_hash)
        return False

    try:
        services.cadastrar_usuario(db, nome or email.split("@")[0], email, senha_hash)
    except services.Conflito:
        # Outro processo cadastrou o mesmo e-mail entre a consulta e o insert
        _redefinir(db, services.buscar_usuario_por_email(db, email), nome, senha_hash)
        return False

    return True


def pedir_senha() -> str:
    senha = getpass.getpass("Nova senha: ")

    if len(senha) < TAMANHO_MINIMO_SENHA:
        sys.exit(f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")

    if getpass.getpass("Confirme a senha: ") != senha:
        sys.exit("As senhas não conferem.")

    return senha


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--nome", help="Nome do usuário (padrão: parte do e-mail)")
    args = parser.parse_args()

    email = models.normalizar_email(args.email)
    senha = pedir_senha()

    with SessionLocal() as db:
        criado = criar_ou_redefinir(db, email, args.nome, senha)

    if criado:
        print(f"Usuário {email} criado com sucesso.")
    else:
        print(f"Senha de {email} redefinida e usuário reativado.")


if __name__ == "__main__":
    main()

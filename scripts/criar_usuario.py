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

from app import models
from app.core.security import gerar_hash_senha
from app.database import SessionLocal

TAMANHO_MINIMO_SENHA = 6


def criar_ou_redefinir(db: Session, email: str, nome: str | None, senha: str) -> bool:
    """Retorna True se criou um usuário novo e False se redefiniu um existente."""

    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == email
    ).first()

    if usuario:
        usuario.senha = gerar_hash_senha(senha)
        usuario.ativo = True

        if nome:
            usuario.nome = nome

        db.commit()
        return False

    db.add(models.Usuario(
        nome=nome or email.split("@")[0],
        email=email,
        senha=gerar_hash_senha(senha),
        ativo=True
    ))
    db.commit()
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

    email = args.email.strip()
    senha = pedir_senha()

    with SessionLocal() as db:
        criado = criar_ou_redefinir(db, email, args.nome, senha)

    if criado:
        print(f"Usuário {email} criado com sucesso.")
    else:
        print(f"Senha de {email} redefinida e usuário reativado.")


if __name__ == "__main__":
    main()

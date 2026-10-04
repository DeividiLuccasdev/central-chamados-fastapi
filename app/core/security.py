from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def gerar_hash_senha(senha: str) -> str:
    return password_hash.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return password_hash.verify(senha, senha_hash)


def criar_token(dados: dict) -> str:
    dados_token = dados.copy()

    expiracao = datetime.now(UTC) + timedelta(
        minutes=settings.jwt_expiracao_minutos
    )

    dados_token.update({
        "exp": expiracao
    })

    return jwt.encode(
        dados_token,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algoritmo
    )


def decodificar_token(token: str) -> dict:
    """Decodifica o token JWT. Lança jwt.InvalidTokenError se for inválido ou expirado."""

    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algoritmo]
    )

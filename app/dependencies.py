from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app import models
from app.core.security import decodificar_token
from app.database import get_db

bearer = HTTPBearer()


class LoginNecessario(Exception):
    """Lançada quando uma página web exige um usuário logado.

    Tratada em app.main, redirecionando para a tela de login.
    """


def obter_usuario_api(
    credenciais: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
) -> models.Usuario:
    """Autenticação da API via token JWT (Authorization: Bearer)."""

    erro = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        dados = decodificar_token(credenciais.credentials)
        usuario_id = int(dados["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise erro

    usuario = db.get(models.Usuario, usuario_id)

    # Tokens de usuários inativados deixam de valer
    if not usuario or not usuario.ativo:
        raise erro

    return usuario


def obter_usuario_web(
    request: Request,
    db: Session = Depends(get_db)
) -> models.Usuario:
    """Autenticação das páginas web via sessão.

    Se o usuário foi inativado (ou removido) depois do login, a sessão é encerrada.
    """

    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        raise LoginNecessario()

    usuario = db.get(models.Usuario, usuario_id)

    if not usuario or not usuario.ativo:
        request.session.clear()
        raise LoginNecessario()

    return usuario

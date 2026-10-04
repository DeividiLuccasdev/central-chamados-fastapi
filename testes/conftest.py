import os

# Configuração mínima para os testes (antes de importar a aplicação)
os.environ.setdefault("JWT_SECRET_KEY", "chave-de-teste-com-pelo-menos-32-bytes")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402
from app.core.security import gerar_hash_senha  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

SENHA_PADRAO = "123456"


@pytest.fixture
def db():
    """Banco SQLite em memória, recriado a cada teste."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)

    sessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    def get_db_teste():
        yield sessao

    app.dependency_overrides[get_db] = get_db_teste

    yield sessao

    app.dependency_overrides.clear()
    sessao.close()
    engine.dispose()


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def criar_usuario(db):
    def _criar(email="admin@teste.com", nome="Admin", ativo=True):
        usuario = models.Usuario(
            nome=nome,
            email=email,
            senha=gerar_hash_senha(SENHA_PADRAO),
            ativo=ativo
        )
        db.add(usuario)
        db.commit()
        return usuario

    return _criar


@pytest.fixture
def auth_api(client, criar_usuario):
    """Cria um usuário e retorna o cabeçalho Authorization com o token dele."""

    usuario = criar_usuario()

    resposta = client.post(
        "/login",
        json={"email": usuario.email, "senha": SENHA_PADRAO}
    )
    assert resposta.status_code == 200

    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


@pytest.fixture
def logado_web(client, criar_usuario):
    """Cria um usuário e faz login pela interface web (cookie de sessão no client)."""

    usuario = criar_usuario()

    resposta = client.post(
        "/login-web",
        data={"email": usuario.email, "senha": SENHA_PADRAO},
        follow_redirects=False
    )
    assert resposta.status_code == 303

    return usuario

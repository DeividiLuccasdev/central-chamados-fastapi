import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base
from main import app, get_db, password_hash


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    sessao = TestingSession()

    def get_db_teste():
        yield sessao

    app.dependency_overrides[get_db] = get_db_teste

    yield sessao

    app.dependency_overrides.pop(get_db)
    sessao.close()


@pytest.fixture
def client(db):
    return TestClient(app)


def criar_usuario(db, email="admin@teste.com", senha="123456", ativo=True):
    usuario = models.Usuario(
        nome="Admin",
        email=email,
        senha=password_hash.hash(senha),
        ativo=ativo
    )
    db.add(usuario)
    db.commit()
    return usuario


def obter_token(client, email="admin@teste.com", senha="123456"):
    resposta = client.post("/login", json={"email": email, "senha": senha})
    assert resposta.status_code == 200
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def test_api_cria_usuario(client, db):
    criar_usuario(db)
    cabecalho = obter_token(client)

    resposta = client.post(
        "/usuarios",
        json={"nome": "Novo", "email": "novo@teste.com", "senha": "123456"},
        headers=cabecalho
    )

    assert resposta.status_code == 200
    assert resposta.json()["email"] == "novo@teste.com"
    assert db.query(models.Usuario).filter_by(email="novo@teste.com").count() == 1


def test_api_login_bloqueia_usuario_inativo(client, db):
    criar_usuario(db, ativo=False)

    resposta = client.post(
        "/login",
        json={"email": "admin@teste.com", "senha": "123456"}
    )

    assert resposta.status_code == 403


def test_api_token_de_usuario_inativado_deixa_de_valer(client, db):
    usuario = criar_usuario(db)
    cabecalho = obter_token(client)

    usuario.ativo = False
    db.commit()

    resposta = client.get("/perfil", headers=cabecalho)

    assert resposta.status_code == 401


def test_api_alterar_status_registra_datas(client, db):
    criar_usuario(db)
    cabecalho = obter_token(client)

    chamado = client.post(
        "/chamados",
        json={"titulo": "Impressora", "descricao": "Sem papel"},
        headers=cabecalho
    ).json()

    resposta = client.patch(
        f"/chamados/{chamado['id']}/status",
        json={"status": "resolvido"},
        headers=cabecalho
    )
    assert resposta.status_code == 200

    salvo = db.get(models.Chamado, chamado["id"])
    db.refresh(salvo)
    assert salvo.status == "resolvido"
    assert salvo.data_atualizacao is not None
    assert salvo.data_fechamento is not None

    client.patch(
        f"/chamados/{chamado['id']}/status",
        json={"status": "aberto"},
        headers=cabecalho
    )

    db.refresh(salvo)
    assert salvo.status == "aberto"
    assert salvo.data_fechamento is None


def test_sessao_web_encerrada_quando_usuario_inativado(client, db):
    usuario = criar_usuario(db)

    resposta = client.post(
        "/login-web",
        data={"email": "admin@teste.com", "senha": "123456"},
        follow_redirects=False
    )
    assert resposta.status_code == 303

    assert client.get("/dashboard", follow_redirects=False).status_code == 200

    usuario.ativo = False
    db.commit()

    resposta = client.get("/dashboard", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login-web"


def test_painel_exige_login(client):
    resposta = client.get("/painel", follow_redirects=True)

    assert str(resposta.url).endswith("/login-web")

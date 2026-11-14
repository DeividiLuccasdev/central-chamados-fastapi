import os

# Configuração mínima para os testes (antes de importar a aplicação)
os.environ.setdefault("JWT_SECRET_KEY", "chave-de-teste-com-pelo-menos-32-bytes")

import threading  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402
from app.core.security import gerar_hash_senha  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

SENHA_PADRAO = "123456"

# Banco PostgreSQL real para os testes de concorrência (marcados com `pg`).
# Sem esta variável eles são pulados; no CI ela aponta para um serviço Postgres.
URL_PG = os.environ.get("TEST_DATABASE_URL")


# PostgreSQL (testes de concorrência)

@pytest.fixture(scope="session")
def pg_engine():
    if not URL_PG:
        pytest.skip("TEST_DATABASE_URL não definida (testes com PostgreSQL)")

    from scripts.criar_tabelas import migrar

    engine = create_engine(URL_PG, pool_size=10)

    # Schema limpo e estrutura criada pelas migrações: testa as migrações também
    with engine.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))

    migrar(URL_PG)

    yield engine

    engine.dispose()


@pytest.fixture
def pg(pg_engine):
    """Uma sessão nova por requisição, como em produção (sem sessão compartilhada).

    Retorna a fábrica de sessões, para o teste preparar e conferir os dados.
    """

    Sessao = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

    def get_db_pg():
        sessao = Sessao()
        try:
            yield sessao
        finally:
            sessao.close()

    app.dependency_overrides[get_db] = get_db_pg

    yield Sessao

    app.dependency_overrides.clear()

    with pg_engine.begin() as conexao:
        conexao.execute(text(
            "TRUNCATE idempotency_keys, chamados, usuarios RESTART IDENTITY CASCADE"
        ))


@pytest.fixture
def sincronizar(monkeypatch):
    """Faz as N primeiras chamadas de `modulo.funcao` se esperarem numa barreira.

    Força a corrida de verdade: todas as requisições passam do mesmo ponto
    (por exemplo, a leitura) antes de qualquer uma seguir para a escrita.
    """

    def _sincronizar(modulo, nome, partes=2, depois=True):
        original = getattr(modulo, nome)
        barreira = threading.Barrier(partes, timeout=15)
        trava = threading.Lock()
        chamadas = 0

        def envolvida(*args, **kwargs):
            nonlocal chamadas

            with trava:
                chamadas += 1
                esperar = chamadas <= partes

            if esperar and not depois:
                barreira.wait()

            resultado = original(*args, **kwargs)

            if esperar and depois:
                barreira.wait()

            return resultado

        monkeypatch.setattr(modulo, nome, envolvida)

    return _sincronizar


def em_paralelo(*funcoes):
    """Roda as funções ao mesmo tempo (cada uma na sua thread) e devolve os resultados."""

    barreira = threading.Barrier(len(funcoes), timeout=15)
    resultados = [None] * len(funcoes)
    erros = []

    def rodar(indice, funcao):
        try:
            barreira.wait()
            resultados[indice] = funcao()
        except Exception as erro:
            erros.append(erro)

    threads = [
        threading.Thread(target=rodar, args=(i, f)) for i, f in enumerate(funcoes)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    if erros:
        raise erros[0]

    return resultados


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


@pytest.fixture
def paralelo():
    return em_paralelo

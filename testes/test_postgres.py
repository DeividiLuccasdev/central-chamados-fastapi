"""Corridas reais contra PostgreSQL: uma sessão/conexão por requisição, em threads.

Rodam quando TEST_DATABASE_URL aponta para um banco descartável (o CI sobe um
serviço Postgres). Sem a variável, são pulados.

A fixture `sincronizar` segura as requisições numa barreira logo depois da
leitura, para que todas vejam o mesmo estado antes de qualquer uma escrever:
assim a corrida acontece sempre, e não só por sorte do agendador.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import models, services
from app.core.security import criar_token, gerar_hash_senha, verificar_senha
from app.main import app

pytestmark = pytest.mark.pg

SENHA_PADRAO = "123456"


def criar_usuario(Sessao, email="admin@teste.com", nome="Admin", ativo=True) -> int:
    with Sessao() as db:
        usuario = models.Usuario(
            nome=nome, email=email, senha=gerar_hash_senha(SENHA_PADRAO), ativo=ativo
        )
        db.add(usuario)
        db.commit()
        return usuario.id


def token(usuario_id: int) -> dict:
    return {"Authorization": f"Bearer {criar_token({'sub': str(usuario_id)})}"}


def contar(Sessao, modelo, *filtros) -> int:
    with Sessao() as db:
        return db.scalar(select(func.count()).select_from(modelo).where(*filtros))


def criar_chamado(Sessao, status="aberto") -> int:
    with Sessao() as db:
        chamado = models.Chamado(titulo="VPN", prioridade="alta", status=status)
        db.add(chamado)
        db.commit()
        return chamado.id


# E-mail

def test_cadastros_simultaneos_com_mesmo_email(pg, paralelo, sincronizar):
    auth = token(criar_usuario(pg))

    # As duas requisições passam pela consulta prévia antes de qualquer insert
    sincronizar(services, "email_em_uso")

    def cadastrar(email):
        return lambda: TestClient(app).post(
            "/usuarios",
            json={"nome": "Novo", "email": email, "senha": "123456"},
            headers=auth
        )

    respostas = paralelo(cadastrar("novo@teste.com"), cadastrar("NOVO@teste.com"))

    assert sorted(r.status_code for r in respostas) == [201, 409]
    assert contar(pg, models.Usuario, func.lower(models.Usuario.email) == "novo@teste.com") == 1


def test_indice_unico_ignora_maiusculas_no_banco(pg):
    criar_usuario(pg, email="a@teste.com")

    from sqlalchemy.exc import IntegrityError

    with pg() as db, pytest.raises(IntegrityError):
        db.add(models.Usuario(nome="B", email="A@TESTE.com", senha="x", ativo=True))
        db.commit()


# Status do chamado

def test_duas_alteracoes_simultaneas_com_mesmo_status_esperado(pg, paralelo, sincronizar):
    auth = token(criar_usuario(pg))
    chamado_id = criar_chamado(pg)

    # As duas leem o chamado "aberto", versão 1, antes de qualquer UPDATE
    sincronizar(services, "alterar_status", depois=False)

    def alterar(novo):
        return lambda: TestClient(app).patch(
            f"/chamados/{chamado_id}/status",
            json={"status": novo, "status_atual": "aberto", "versao": 1},
            headers=auth
        )

    respostas = paralelo(alterar("resolvido"), alterar("em andamento"))

    assert sorted(r.status_code for r in respostas) == [200, 409]

    vencedora = next(r for r in respostas if r.status_code == 200).json()
    with pg() as db:
        chamado = db.get(models.Chamado, chamado_id)
        assert chamado.status == vencedora["status"]
        assert chamado.versao == 2


def test_alteracoes_simultaneas_sem_status_esperado(pg, paralelo, sincronizar):
    auth = token(criar_usuario(pg))
    chamado_id = criar_chamado(pg)

    sincronizar(services, "alterar_status", depois=False)

    def resolver():
        return TestClient(app).patch(
            f"/chamados/{chamado_id}/status", json={"status": "resolvido"}, headers=auth
        )

    respostas = paralelo(resolver, resolver)

    # Uma vence; a outra não sobrescreve às cegas (nem gera 500)
    assert sorted(r.status_code for r in respostas) == [200, 409]
    assert contar(pg, models.Chamado, models.Chamado.versao == 2) == 1


def test_alteracao_atrasada_apos_resolver_preserva_fechamento(pg):
    auth = token(criar_usuario(pg))
    chamado_id = criar_chamado(pg)
    client = TestClient(app)
    url = f"/chamados/{chamado_id}/status"

    resolvido = client.patch(url, json={"status": "resolvido"}, headers=auth).json()

    atrasada = client.patch(
        url, json={"status": "em andamento", "status_atual": "aberto", "versao": 1},
        headers=auth
    )

    assert atrasada.status_code == 409

    atual = client.get(f"/chamados/{chamado_id}", headers=auth).json()
    assert atual["status"] == "resolvido"
    assert atual["data_fechamento"] == resolvido["data_fechamento"]
    assert atual["data_fechamento"] is not None


def test_datas_vem_do_relogio_do_banco(pg):
    auth = token(criar_usuario(pg))
    chamado_id = criar_chamado(pg)

    resposta = TestClient(app).patch(
        f"/chamados/{chamado_id}/status", json={"status": "resolvido"}, headers=auth
    ).json()

    from datetime import datetime

    criacao, atualizacao, fechamento = (
        datetime.fromisoformat(resposta[campo])
        for campo in ("data_criacao", "data_atualizacao", "data_fechamento")
    )

    # Mesmo relógio (o do banco) e mesma transação para as duas datas
    assert atualizacao == fechamento
    assert atualizacao >= criacao


# Idempotency-Key

def test_mesma_chave_em_paralelo_cria_um_chamado_so(pg, paralelo, sincronizar):
    auth = token(criar_usuario(pg))

    # As duas não encontram a chave antes de qualquer uma gravar
    sincronizar(services, "_buscar_chave")

    def criar():
        return TestClient(app).post(
            "/chamados",
            json={"titulo": "Impressora", "descricao": "Sem papel"},
            headers={**auth, "Idempotency-Key": "chave-unica"}
        )

    respostas = paralelo(criar, criar)

    assert [r.status_code for r in respostas] == [201, 201]
    assert respostas[0].json() == respostas[1].json()
    assert sorted(r.headers["Idempotent-Replayed"] for r in respostas) == ["false", "true"]
    assert contar(pg, models.Chamado) == 1
    assert contar(pg, models.ChaveIdempotencia) == 1


def test_mesma_chave_com_outro_corpo(pg):
    auth = {**token(criar_usuario(pg)), "Idempotency-Key": "chave-unica"}
    client = TestClient(app)

    primeira = client.post("/chamados", json={"titulo": "A", "descricao": "x"}, headers=auth)
    segunda = client.post("/chamados", json={"titulo": "B", "descricao": "x"}, headers=auth)

    assert primeira.status_code == 201
    assert segunda.status_code == 422
    assert contar(pg, models.Chamado) == 1


# Inativação de usuários

def test_ultimos_dois_ativos_se_inativando_ao_mesmo_tempo(pg, paralelo, sincronizar):
    ana = criar_usuario(pg, email="ana@teste.com", nome="Ana")
    bia = criar_usuario(pg, email="bia@teste.com", nome="Bia")

    clientes = {}
    for usuario_id, email in ((ana, "ana@teste.com"), (bia, "bia@teste.com")):
        cliente = TestClient(app)
        resposta = cliente.post(
            "/login-web",
            data={"email": email, "senha": SENHA_PADRAO},
            follow_redirects=False
        )
        assert resposta.status_code == 303
        clientes[usuario_id] = cliente

    # As duas já passaram pela checagem de login (ambas ativas) antes da trava
    sincronizar(services, "inativar_usuario", depois=False)

    def inativar(ator, alvo):
        return lambda: clientes[ator].post(
            f"/usuarios/{alvo}/inativar", follow_redirects=False
        )

    respostas = paralelo(inativar(ana, bia), inativar(bia, ana))

    assert sorted(r.status_code for r in respostas) == [303, 409]
    assert contar(pg, models.Usuario, models.Usuario.ativo.is_(True)) == 1


# Migrações

def test_migracoes_batem_com_os_modelos(pg, pg_engine):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.database import Base

    with pg_engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), Base.metadata)

    assert diferencas == []


# Usuário de demonstração

def test_dois_conteineres_criando_a_demo_ao_mesmo_tempo(pg, paralelo, sincronizar):
    from scripts.criar_usuario_demo import EMAIL_DEMO, SENHA_DEMO, garantir_usuario_demo

    # Os dois passam pela consulta prévia antes de qualquer insert
    sincronizar(services, "email_em_uso")

    def criar():
        with pg() as db:
            return garantir_usuario_demo(db)

    assert sorted(paralelo(criar, criar)) == [False, True]

    with pg() as db:
        usuario = services.buscar_usuario_por_email(db, EMAIL_DEMO)
        assert usuario.ativo is True
        assert verificar_senha(SENHA_DEMO, usuario.senha)

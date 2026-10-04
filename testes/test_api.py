from app import models

SENHA_PADRAO = "123456"


# Autenticação

def test_login_retorna_token(client, criar_usuario):
    criar_usuario()

    resposta = client.post(
        "/login",
        json={"email": "admin@teste.com", "senha": SENHA_PADRAO}
    )

    assert resposta.status_code == 200
    assert resposta.json()["token_type"] == "bearer"
    assert resposta.json()["access_token"]


def test_login_senha_errada(client, criar_usuario):
    criar_usuario()

    resposta = client.post(
        "/login",
        json={"email": "admin@teste.com", "senha": "errada"}
    )

    assert resposta.status_code == 401


def test_login_bloqueia_usuario_inativo(client, criar_usuario):
    criar_usuario(ativo=False)

    resposta = client.post(
        "/login",
        json={"email": "admin@teste.com", "senha": SENHA_PADRAO}
    )

    assert resposta.status_code == 403


def test_perfil_exige_token(client):
    assert client.get("/perfil").status_code == 401


def test_perfil_com_token_invalido(client, db):
    resposta = client.get("/perfil", headers={"Authorization": "Bearer invalido"})

    assert resposta.status_code == 401


def test_perfil(client, auth_api):
    resposta = client.get("/perfil", headers=auth_api)

    assert resposta.status_code == 200
    assert resposta.json()["email"] == "admin@teste.com"
    assert "senha" not in resposta.json()


def test_token_de_usuario_inativado_deixa_de_valer(client, db, auth_api):
    usuario = db.query(models.Usuario).one()
    usuario.ativo = False
    db.commit()

    assert client.get("/perfil", headers=auth_api).status_code == 401


# Usuários

def test_criar_usuario(client, db, auth_api):
    resposta = client.post(
        "/usuarios",
        json={"nome": "Novo", "email": "novo@teste.com", "senha": "123456"},
        headers=auth_api
    )

    assert resposta.status_code == 201
    assert resposta.json()["email"] == "novo@teste.com"
    assert "senha" not in resposta.json()
    assert db.query(models.Usuario).filter_by(email="novo@teste.com").count() == 1


def test_criar_usuario_exige_token(client, db):
    resposta = client.post(
        "/usuarios",
        json={"nome": "Novo", "email": "novo@teste.com", "senha": "123456"}
    )

    assert resposta.status_code == 401


def test_criar_usuario_senha_curta(client, auth_api):
    resposta = client.post(
        "/usuarios",
        json={"nome": "Novo", "email": "novo@teste.com", "senha": "123"},
        headers=auth_api
    )

    assert resposta.status_code == 422


def test_criar_usuario_email_duplicado(client, auth_api):
    resposta = client.post(
        "/usuarios",
        json={"nome": "Outro", "email": "admin@teste.com", "senha": "123456"},
        headers=auth_api
    )

    assert resposta.status_code == 409


# Chamados

def criar_chamado(client, auth_api, **dados):
    corpo = {"titulo": "Impressora", "descricao": "Sem papel", **dados}
    resposta = client.post("/chamados", json=corpo, headers=auth_api)
    assert resposta.status_code == 201
    return resposta.json()


def test_criar_chamado(client, auth_api):
    chamado = criar_chamado(client, auth_api, prioridade="Alta")

    assert chamado["status"] == "aberto"
    assert chamado["prioridade"] == "alta"
    assert chamado["data_criacao"]


def test_criar_chamado_prioridade_invalida(client, auth_api):
    resposta = client.post(
        "/chamados",
        json={"titulo": "X", "descricao": "Y", "prioridade": "urgentissima"},
        headers=auth_api
    )

    assert resposta.status_code == 422


def test_listar_e_filtrar_chamados(client, auth_api):
    criar_chamado(client, auth_api, titulo="A", prioridade="alta")
    criar_chamado(client, auth_api, titulo="B", prioridade="baixa")

    todos = client.get("/chamados", headers=auth_api).json()
    altos = client.get("/chamados?prioridade=alta", headers=auth_api).json()

    assert len(todos) == 2
    assert [c["titulo"] for c in altos] == ["A"]


def test_obter_chamado(client, auth_api):
    chamado = criar_chamado(client, auth_api)

    resposta = client.get(f"/chamados/{chamado['id']}", headers=auth_api)

    assert resposta.status_code == 200
    assert resposta.json()["titulo"] == "Impressora"


def test_obter_chamado_inexistente(client, auth_api):
    assert client.get("/chamados/999", headers=auth_api).status_code == 404


def test_alterar_status_registra_datas(client, auth_api):
    chamado = criar_chamado(client, auth_api)
    url = f"/chamados/{chamado['id']}/status"

    resolvido = client.patch(url, json={"status": "Resolvido"}, headers=auth_api).json()

    assert resolvido["status"] == "resolvido"
    assert resolvido["data_atualizacao"]
    assert resolvido["data_fechamento"]

    reaberto = client.patch(url, json={"status": "aberto"}, headers=auth_api).json()

    assert reaberto["status"] == "aberto"
    assert reaberto["data_fechamento"] is None


def test_alterar_status_invalido(client, auth_api):
    chamado = criar_chamado(client, auth_api)

    resposta = client.patch(
        f"/chamados/{chamado['id']}/status",
        json={"status": "cancelado"},
        headers=auth_api
    )

    assert resposta.status_code == 422

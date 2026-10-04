import pytest

from app import models


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_pagina_login(client):
    resposta = client.get("/login-web")

    assert resposta.status_code == 200
    assert "Central de Chamados" in resposta.text


def test_raiz_redireciona_para_login_sem_sessao(client):
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert str(resposta.url).endswith("/login-web")


@pytest.mark.parametrize("url", [
    "/dashboard",
    "/painel",
    "/chamados-web",
    "/novo-chamado",
    "/novo-usuario",
    "/usuarios-web",
    "/chamados/1/ver",
    "/chamados/1/status",
])
def test_paginas_exigem_login(client, url):
    resposta = client.get(url, follow_redirects=True)

    assert str(resposta.url).endswith("/login-web")


def test_login_web_senha_errada(client, criar_usuario):
    criar_usuario()

    resposta = client.post(
        "/login-web",
        data={"email": "admin@teste.com", "senha": "errada"}
    )

    assert resposta.status_code == 401
    assert "E-mail ou senha inválidos" in resposta.text


def test_login_web_usuario_inativo(client, criar_usuario):
    criar_usuario(ativo=False)

    resposta = client.post(
        "/login-web",
        data={"email": "admin@teste.com", "senha": "123456"}
    )

    assert resposta.status_code == 403


def test_dashboard(client, logado_web):
    resposta = client.get("/dashboard")

    assert resposta.status_code == 200
    assert "Dashboard" in resposta.text


def test_sessao_encerrada_quando_usuario_inativado(client, db, logado_web):
    logado_web.ativo = False
    db.commit()

    resposta = client.get("/dashboard", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login-web"


def test_logout(client, logado_web):
    client.get("/logout")

    resposta = client.get("/dashboard", follow_redirects=False)

    assert resposta.status_code == 303


def test_criar_chamado_e_alterar_status(client, db, logado_web):
    client.post(
        "/novo-chamado",
        data={"titulo": "Erro no ERP", "descricao": "Tela travada", "prioridade": "alta"}
    )

    chamado = db.query(models.Chamado).one()
    assert chamado.status == "aberto"
    assert chamado.usuario_id == logado_web.id

    client.post(f"/chamados/{chamado.id}/status", data={"status": "resolvido"})

    db.refresh(chamado)
    assert chamado.status == "resolvido"
    assert chamado.data_fechamento is not None


def test_criar_chamado_prioridade_invalida(client, logado_web):
    resposta = client.post(
        "/novo-chamado",
        data={"titulo": "X", "descricao": "Y", "prioridade": "qualquer"}
    )

    assert resposta.status_code == 400


def test_filtrar_chamados(client, db, logado_web):
    db.add_all([
        models.Chamado(titulo="VPN caindo", prioridade="alta", status="aberto"),
        models.Chamado(titulo="Troca de mouse", prioridade="baixa", status="resolvido"),
    ])
    db.commit()

    resposta = client.get("/chamados-web?status=resolvido")

    assert "Troca de mouse" in resposta.text
    assert "VPN caindo" not in resposta.text.split("<tbody>")[1]


def test_busca_trata_curinga_como_texto(client, db, logado_web):
    db.add(models.Chamado(titulo="VPN caindo", prioridade="alta", status="aberto"))
    db.commit()

    resposta = client.get("/chamados-web?busca=%25")

    assert "VPN caindo" not in resposta.text.split("<tbody>")[1]


def test_novo_usuario_email_duplicado(client, logado_web):
    resposta = client.post(
        "/novo-usuario",
        data={"nome": "Outro", "email": "admin@teste.com", "senha": "123456"}
    )

    assert resposta.status_code == 400
    assert "Já existe um usuário com este e-mail." in resposta.text


def test_nao_pode_inativar_a_si_mesmo(client, logado_web):
    resposta = client.post(f"/usuarios/{logado_web.id}/inativar")

    assert resposta.status_code == 400


def test_inativar_e_ativar_usuario(client, db, criar_usuario, logado_web):
    outro = criar_usuario(email="maria@teste.com", nome="Maria")

    client.post(f"/usuarios/{outro.id}/inativar")
    db.refresh(outro)
    assert outro.ativo is False

    client.post(f"/usuarios/{outro.id}/ativar")
    db.refresh(outro)
    assert outro.ativo is True

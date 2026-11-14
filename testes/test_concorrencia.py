"""Regras de concorrência e idempotência (rápidos, em SQLite).

As corridas de verdade, com várias conexões ao mesmo tempo, estão em
test_postgres.py.
"""

import pytest

from app import models, services

SENHA_PADRAO = "123456"


def criar_chamado(client, auth_api, **dados):
    corpo = {"titulo": "Impressora", "descricao": "Sem papel", **dados}
    resposta = client.post("/chamados", json=corpo, headers=auth_api)
    assert resposta.status_code == 201
    return resposta.json()


def alterar(client, auth_api, chamado_id, **corpo):
    return client.patch(f"/chamados/{chamado_id}/status", json=corpo, headers=auth_api)


# Status do chamado

def test_chamado_novo_comeca_na_versao_1(client, auth_api):
    assert criar_chamado(client, auth_api)["versao"] == 1


def test_alterar_status_incrementa_versao(client, auth_api):
    chamado = criar_chamado(client, auth_api)

    resposta = alterar(client, auth_api, chamado["id"], status="em andamento")

    assert resposta.status_code == 200
    assert resposta.json()["versao"] == 2


def test_formulario_antigo_nao_reabre_chamado_resolvido(client, auth_api):
    chamado = criar_chamado(client, auth_api)
    resolvido = alterar(client, auth_api, chamado["id"], status="resolvido").json()

    # Alguém com a tela antiga (ainda "aberto") pede "em andamento"
    resposta = alterar(client, auth_api, chamado["id"], status="em andamento")

    assert resposta.status_code == 409

    atual = client.get(f"/chamados/{chamado['id']}", headers=auth_api).json()
    assert atual["status"] == "resolvido"
    assert atual["data_fechamento"] == resolvido["data_fechamento"]


def test_status_atual_divergente_retorna_409(client, auth_api):
    chamado = criar_chamado(client, auth_api)
    alterar(client, auth_api, chamado["id"], status="resolvido")

    resposta = alterar(
        client, auth_api, chamado["id"], status="aberto", status_atual="aberto"
    )

    assert resposta.status_code == 409


def test_versao_divergente_retorna_409(client, auth_api):
    chamado = criar_chamado(client, auth_api)
    alterar(client, auth_api, chamado["id"], status="em andamento")

    resposta = alterar(client, auth_api, chamado["id"], status="resolvido", versao=1)

    assert resposta.status_code == 409
    assert resposta.json()["detail"]


def test_status_e_versao_corretos_alteram(client, auth_api):
    chamado = criar_chamado(client, auth_api)

    resposta = alterar(
        client, auth_api, chamado["id"],
        status="resolvido", status_atual="aberto", versao=1
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "resolvido"


def test_pedir_o_mesmo_status_e_idempotente(client, auth_api):
    chamado = criar_chamado(client, auth_api)
    primeiro = alterar(client, auth_api, chamado["id"], status="resolvido").json()

    segundo = alterar(client, auth_api, chamado["id"], status="resolvido")

    assert segundo.status_code == 200
    assert segundo.json()["versao"] == primeiro["versao"]
    assert segundo.json()["data_fechamento"] == primeiro["data_fechamento"]


def test_reabrir_explicitamente_continua_permitido(client, auth_api):
    chamado = criar_chamado(client, auth_api)
    alterar(client, auth_api, chamado["id"], status="resolvido")

    resposta = alterar(
        client, auth_api, chamado["id"], status="aberto", status_atual="resolvido"
    )

    assert resposta.status_code == 200
    assert resposta.json()["data_fechamento"] is None


@pytest.mark.parametrize("origem, destino, permitido", [
    ("aberto", "em andamento", True),
    ("aberto", "resolvido", True),
    ("em andamento", "aberto", True),
    ("em andamento", "resolvido", True),
    ("resolvido", "aberto", True),
    ("resolvido", "em andamento", False),
])
def test_tabela_de_transicoes(db, origem, destino, permitido):
    chamado = models.Chamado(titulo="X", prioridade="media", status=origem)
    db.add(chamado)
    db.commit()

    if permitido:
        assert services.alterar_status(db, chamado, destino).status == destino
    else:
        with pytest.raises(services.Conflito):
            services.alterar_status(db, chamado, destino)


def test_web_status_com_tela_desatualizada_mostra_conflito(client, db, logado_web):
    chamado = models.Chamado(titulo="VPN", prioridade="alta", status="aberto")
    db.add(chamado)
    db.commit()

    # Outra pessoa resolve o chamado...
    services.alterar_status(db, chamado, "resolvido")

    # ...e este formulário ainda mostra "aberto", versão 1
    resposta = client.post(
        f"/chamados/{chamado.id}/status",
        data={"status": "em andamento", "status_atual": "aberto", "versao": "1"}
    )

    assert resposta.status_code == 409
    assert "alterado por outra pessoa" in resposta.text

    db.refresh(chamado)
    assert chamado.status == "resolvido"
    assert chamado.data_fechamento is not None


def test_web_formulario_de_status_envia_status_e_versao(client, db, logado_web):
    chamado = models.Chamado(titulo="VPN", prioridade="alta", status="aberto")
    db.add(chamado)
    db.commit()

    resposta = client.get(f"/chamados/{chamado.id}/status")

    assert 'name="status_atual" value="aberto"' in resposta.text
    assert 'name="versao" value="1"' in resposta.text


# E-mail único

def test_email_duplicado_ignora_maiusculas(client, auth_api):
    resposta = client.post(
        "/usuarios",
        json={"nome": "Outro", "email": " ADMIN@Teste.com ", "senha": "123456"},
        headers=auth_api
    )

    assert resposta.status_code == 409


def test_email_e_gravado_normalizado(client, db, auth_api):
    resposta = client.post(
        "/usuarios",
        json={"nome": "Novo", "email": " Novo@Teste.COM", "senha": "123456"},
        headers=auth_api
    )

    assert resposta.status_code == 201
    assert resposta.json()["email"] == "novo@teste.com"


def test_login_ignora_maiusculas_no_email(client, criar_usuario):
    criar_usuario()

    resposta = client.post("/login", json={"email": "Admin@Teste.com", "senha": SENHA_PADRAO})

    assert resposta.status_code == 200


def test_integrity_error_vira_409_na_api(client, db, auth_api, monkeypatch):
    # Simula a corrida: a consulta prévia não vê o outro cadastro (ainda não
    # commitado), então quem barra o duplicado é o índice único do banco
    monkeypatch.setattr(services, "email_em_uso", lambda db, email: False)

    resposta = client.post(
        "/usuarios",
        json={"nome": "Outro", "email": "ADMIN@teste.com", "senha": "123456"},
        headers=auth_api
    )

    assert resposta.status_code == 409
    assert db.query(models.Usuario).count() == 1


def test_integrity_error_vira_erro_no_formulario_web(client, db, logado_web, monkeypatch):
    monkeypatch.setattr(services, "email_em_uso", lambda db, email: False)

    resposta = client.post(
        "/novo-usuario",
        data={"nome": "Outro", "email": "Admin@Teste.com", "senha": "123456"}
    )

    assert resposta.status_code == 400
    assert "Já existe um usuário com este e-mail." in resposta.text
    assert db.query(models.Usuario).count() == 1


def test_script_criar_usuario_trata_maiusculas(db, criar_usuario):
    from scripts.criar_usuario import criar_ou_redefinir

    criar_usuario()

    assert criar_ou_redefinir(db, "ADMIN@teste.com", None, "outrasenha") is False
    assert db.query(models.Usuario).count() == 1


# Idempotency-Key

def post_chamado(client, auth_api, chave, **dados):
    corpo = {"titulo": "Impressora", "descricao": "Sem papel", **dados}
    return client.post(
        "/chamados", json=corpo, headers={**auth_api, "Idempotency-Key": chave}
    )


def test_mesma_chave_cria_um_chamado_so(client, db, auth_api):
    primeira = post_chamado(client, auth_api, "chave-1")
    segunda = post_chamado(client, auth_api, "chave-1")

    assert primeira.status_code == segunda.status_code == 201
    assert primeira.json() == segunda.json()
    assert primeira.headers["Idempotent-Replayed"] == "false"
    assert segunda.headers["Idempotent-Replayed"] == "true"
    assert db.query(models.Chamado).count() == 1


def test_mesma_chave_com_outro_corpo_retorna_422(client, db, auth_api):
    post_chamado(client, auth_api, "chave-1")

    resposta = post_chamado(client, auth_api, "chave-1", titulo="Outro título")

    assert resposta.status_code == 422
    assert db.query(models.Chamado).count() == 1


def test_chaves_diferentes_criam_chamados_diferentes(client, db, auth_api):
    post_chamado(client, auth_api, "chave-1")
    post_chamado(client, auth_api, "chave-2")

    assert db.query(models.Chamado).count() == 2


def test_chave_e_separada_por_usuario(client, db, criar_usuario, auth_api):
    from app.core.security import criar_token

    outro = criar_usuario(email="maria@teste.com", nome="Maria")
    auth_outro = {"Authorization": f"Bearer {criar_token({'sub': str(outro.id)})}"}

    post_chamado(client, auth_api, "mesma-chave")
    resposta = post_chamado(client, auth_outro, "mesma-chave")

    assert resposta.status_code == 201
    assert resposta.json()["usuario_id"] == outro.id
    assert db.query(models.Chamado).count() == 2


def test_chave_invalida_retorna_400(client, auth_api):
    assert post_chamado(client, auth_api, "x" * 256).status_code == 400


def test_sem_chave_continua_criando_normalmente(client, db, auth_api):
    criar_chamado(client, auth_api)
    criar_chamado(client, auth_api)

    assert db.query(models.Chamado).count() == 2


def test_formulario_web_tem_chave_de_uso_unico(client, logado_web):
    primeira = client.get("/novo-chamado").text
    segunda = client.get("/novo-chamado").text

    assert 'name="chave_idempotencia"' in primeira

    def chave(html):
        return html.split('name="chave_idempotencia"')[1].split('value="')[1].split('"')[0]

    assert chave(primeira) != chave(segunda)


def test_formulario_web_reenviado_cria_um_chamado_so(client, db, logado_web):
    dados = {
        "titulo": "Erro no ERP",
        "descricao": "Tela travada",
        "prioridade": "alta",
        "chave_idempotencia": "8f6c1f1e-0000-4000-8000-000000000001"
    }

    primeira = client.post("/novo-chamado", data=dados, follow_redirects=False)
    segunda = client.post("/novo-chamado", data=dados, follow_redirects=False)

    assert primeira.status_code == segunda.status_code == 303
    assert db.query(models.Chamado).count() == 1


# Inativação de usuários

def test_inativar_com_ator_ja_inativo_e_recusado(db, criar_usuario):
    ator = criar_usuario()
    alvo = criar_usuario(email="maria@teste.com", nome="Maria")

    ator.ativo = False
    db.commit()

    with pytest.raises(services.Conflito):
        services.inativar_usuario(db, ator_id=ator.id, alvo_id=alvo.id)

    db.refresh(alvo)
    assert alvo.ativo is True


def test_inativar_usuario_ja_inativo_e_idempotente(client, db, criar_usuario, logado_web):
    outro = criar_usuario(email="maria@teste.com", nome="Maria", ativo=False)

    resposta = client.post(f"/usuarios/{outro.id}/inativar", follow_redirects=False)

    assert resposta.status_code == 303

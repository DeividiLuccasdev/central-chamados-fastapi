"""Login público de demonstração: criação no deploy e proteção da conta."""

import pytest

from app import models, services
from app.core.config import Settings
from app.core.security import gerar_hash_senha, verificar_senha
from scripts import criar_usuario_demo as script
from scripts.criar_usuario_demo import EMAIL_DEMO, NOME_DEMO, SENHA_DEMO, garantir_usuario_demo


def configurar(monkeypatch, **variaveis):
    for nome in ("RENDER", "CRIAR_USUARIO_DEMO"):
        monkeypatch.delenv(nome, raising=False)

    for nome, valor in variaveis.items():
        monkeypatch.setenv(nome, valor)

    return Settings(_env_file=None)


def usuarios_demo(db):
    return db.query(models.Usuario).filter(models.Usuario.email == EMAIL_DEMO).all()


# Criação (seed)

def test_cria_usuario_demo(db):
    assert garantir_usuario_demo(db) is True

    usuario = usuarios_demo(db)[0]
    assert usuario.nome == NOME_DEMO
    assert usuario.ativo is True
    assert verificar_senha(SENHA_DEMO, usuario.senha)


def test_criar_de_novo_e_idempotente(db):
    garantir_usuario_demo(db)

    assert garantir_usuario_demo(db) is False
    assert len(usuarios_demo(db)) == 1


def test_restaura_demo_inativada_e_com_senha_trocada(db):
    garantir_usuario_demo(db)

    usuario = usuarios_demo(db)[0]
    usuario.ativo = False
    usuario.nome = "Vandalizado"
    usuario.senha = gerar_hash_senha("outrasenha")
    db.commit()

    garantir_usuario_demo(db)

    db.refresh(usuario)
    assert usuario.ativo is True
    assert usuario.nome == NOME_DEMO
    assert verificar_senha(SENHA_DEMO, usuario.senha)


def test_login_web_com_credenciais_publicadas(client, db):
    garantir_usuario_demo(db)

    resposta = client.post(
        "/login-web",
        data={"email": EMAIL_DEMO, "senha": SENHA_DEMO},
        follow_redirects=False
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/dashboard"


def test_login_api_com_credenciais_publicadas(client, db):
    garantir_usuario_demo(db)

    resposta = client.post("/login", json={"email": EMAIL_DEMO, "senha": SENHA_DEMO})

    assert resposta.status_code == 200


# Quando o seed roda

@pytest.fixture
def sessao_do_script(db, monkeypatch):
    """Faz o script usar o banco de teste e conta quantas sessões ele abriu."""

    aberturas = []

    def sessao_local():
        aberturas.append(1)
        return db

    monkeypatch.setattr(script, "SessionLocal", sessao_local)
    return aberturas


def test_sem_variavel_nao_cria_nada(db, monkeypatch, sessao_do_script):
    script.main(configurar(monkeypatch))

    assert sessao_do_script == []
    assert usuarios_demo(db) == []


@pytest.mark.parametrize("variavel", ["RENDER", "CRIAR_USUARIO_DEMO"])
def test_cria_no_render_ou_com_variavel_explicita(db, monkeypatch, sessao_do_script, variavel):
    script.main(configurar(monkeypatch, **{variavel: "true"}))

    assert len(usuarios_demo(db)) == 1


def test_variavel_explicita_false_nao_cria(db, monkeypatch, sessao_do_script):
    script.main(configurar(monkeypatch, CRIAR_USUARIO_DEMO="false"))

    assert usuarios_demo(db) == []


# Proteção da conta

def test_eh_usuario_demo_ignora_maiusculas():
    assert services.eh_usuario_demo(models.Usuario(email="Demo@Example.com"))
    assert not services.eh_usuario_demo(models.Usuario(email="admin@teste.com"))
    assert not services.eh_usuario_demo(None)


def test_web_nao_inativa_usuario_demo(client, db, logado_web):
    garantir_usuario_demo(db)
    demo = usuarios_demo(db)[0]

    resposta = client.post(f"/usuarios/{demo.id}/inativar", follow_redirects=False)

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == services.MENSAGEM_USUARIO_DEMO

    db.refresh(demo)
    assert demo.ativo is True


def test_servico_nao_inativa_usuario_demo(db, criar_usuario):
    ator = criar_usuario()
    garantir_usuario_demo(db)
    demo = usuarios_demo(db)[0]

    with pytest.raises(services.UsuarioProtegido):
        services.inativar_usuario(db, ator_id=ator.id, alvo_id=demo.id)

    db.refresh(demo)
    assert demo.ativo is True


def test_api_nao_recadastra_o_email_da_demo(client, db, auth_api):
    garantir_usuario_demo(db)

    resposta = client.post(
        "/usuarios",
        json={"nome": "Outro", "email": "DEMO@example.com", "senha": "123456"},
        headers=auth_api
    )

    assert resposta.status_code == 409
    assert verificar_senha(SENHA_DEMO, usuarios_demo(db)[0].senha)


def test_lista_de_usuarios_nao_mostra_inativar_para_a_demo(client, db, logado_web):
    garantir_usuario_demo(db)
    demo = usuarios_demo(db)[0]

    resposta = client.get("/usuarios-web")

    assert "Conta de demonstração" in resposta.text
    assert f"/usuarios/{demo.id}/inativar" not in resposta.text


@pytest.fixture
def logado_como_demo(client, db):
    garantir_usuario_demo(db)

    resposta = client.post(
        "/login-web",
        data={"email": EMAIL_DEMO, "senha": SENHA_DEMO},
        follow_redirects=False
    )
    assert resposta.status_code == 303

    return usuarios_demo(db)[0]


def test_demo_logada_nao_inativa_outros(client, db, criar_usuario, logado_como_demo):
    dono = criar_usuario()

    resposta = client.post(f"/usuarios/{dono.id}/inativar", follow_redirects=False)

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == services.MENSAGEM_DEMO_SEM_GERENCIAR
    db.refresh(dono)
    assert dono.ativo is True


def test_demo_logada_nao_ativa_outros(client, db, criar_usuario, logado_como_demo):
    inativo = criar_usuario(ativo=False)

    resposta = client.post(f"/usuarios/{inativo.id}/ativar", follow_redirects=False)

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == services.MENSAGEM_DEMO_SEM_GERENCIAR
    db.refresh(inativo)
    assert inativo.ativo is False


def test_servico_recusa_demo_como_ator(db, criar_usuario):
    dono = criar_usuario()
    inativo = criar_usuario(email="maria@teste.com", nome="Maria", ativo=False)
    garantir_usuario_demo(db)
    demo = usuarios_demo(db)[0]

    with pytest.raises(services.UsuarioProtegido):
        services.inativar_usuario(db, ator_id=demo.id, alvo_id=dono.id)

    with pytest.raises(services.UsuarioProtegido):
        services.ativar_usuario(db, ator=demo, alvo=inativo)

    db.refresh(dono)
    db.refresh(inativo)
    assert dono.ativo is True
    assert inativo.ativo is False


def test_demo_logada_nao_ve_botoes_de_ativar_e_inativar(
    client, db, criar_usuario, logado_como_demo
):
    dono = criar_usuario()
    inativo = criar_usuario(email="maria@teste.com", nome="Maria", ativo=False)

    resposta = client.get("/usuarios-web")

    assert resposta.status_code == 200
    assert f"/usuarios/{dono.id}/inativar" not in resposta.text
    assert f"/usuarios/{inativo.id}/ativar" not in resposta.text
    assert "Indisponível na demonstração" in resposta.text


def test_demo_logada_continua_cadastrando_usuarios(client, db, logado_como_demo):
    resposta = client.post(
        "/novo-usuario",
        data={"nome": "Novo", "email": "novo@teste.com", "senha": "123456"},
        follow_redirects=False
    )

    assert resposta.status_code == 303
    assert services.buscar_usuario_por_email(db, "novo@teste.com") is not None

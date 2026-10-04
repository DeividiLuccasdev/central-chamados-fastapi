from app import models
from app.core.security import verificar_senha
from scripts.criar_usuario import criar_ou_redefinir


def test_cria_usuario_novo(db):
    assert criar_ou_redefinir(db, "novo@teste.com", "Novo", "segredo1") is True

    usuario = db.query(models.Usuario).one()
    assert usuario.nome == "Novo"
    assert usuario.ativo is True
    assert verificar_senha("segredo1", usuario.senha)


def test_redefine_senha_e_reativa_usuario_existente(db, criar_usuario):
    usuario = criar_usuario(ativo=False)

    assert criar_ou_redefinir(db, usuario.email, None, "outrasenha") is False

    db.refresh(usuario)
    assert usuario.ativo is True
    assert usuario.nome == "Admin"
    assert verificar_senha("outrasenha", usuario.senha)


def test_login_funciona_apos_redefinir(client, db, criar_usuario):
    usuario = criar_usuario()
    criar_ou_redefinir(db, usuario.email, None, "senhanova")

    resposta = client.post(
        "/login-web",
        data={"email": usuario.email, "senha": "senhanova"},
        follow_redirects=False
    )

    assert resposta.status_code == 303

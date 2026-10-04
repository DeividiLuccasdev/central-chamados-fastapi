from fastapi.testclient import TestClient
from main import app, validar_token

client = TestClient(app)


def test_rota_principal():
    response = client.get("/")

    assert response.status_code == 200

def test_pagina_login():
    resposta = client.get("/login-web")

    assert resposta.status_code == 200
    assert "Central de Chamados" in resposta.text

def test_dashboard_exige_login():
    resposta = client.get(
        "/dashboard",
        follow_redirects=False
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login-web"

def test_usuario_senha_curta():
    # A rota exige token; simula um usuário autenticado
    app.dependency_overrides[validar_token] = lambda: {"sub": "1"}

    try:
        resposta = client.post(
            "/usuarios",
            json={
                "nome": "Usuario Teste",
                "email": "teste@teste.com",
                "senha": "123"
            }
        )
    finally:
        app.dependency_overrides.pop(validar_token)

    assert resposta.status_code == 422


def test_criar_usuario_exige_token():
    resposta = client.post(
        "/usuarios",
        json={
            "nome": "Usuario Teste",
            "email": "teste@teste.com",
            "senha": "123456"
        }
    )

    assert resposta.status_code == 401
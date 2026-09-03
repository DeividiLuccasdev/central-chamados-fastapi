from fastapi.testclient import TestClient
from main import app

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
    resposta = client.post(
        "/usuarios",
        json={
            "nome": "Usuario Teste",
            "email": "teste@teste.com",
            "senha": "123"
        }
    )

    assert resposta.status_code == 422
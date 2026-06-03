import os

from fastapi.testclient import TestClient

from app.main import app


def test_endpoints_exigem_token() -> None:
    with TestClient(app) as client:
        resposta = client.get("/admin/sincronizacoes")
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Token de acesso invalido."


def test_healthcheck_nao_exige_token() -> None:
    with TestClient(app) as client:
        resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_login_retorna_token_com_credenciais_validas() -> None:
    username = os.environ.get("TUCANO_CVM_USERNAME", "frontend-teste")
    password = os.environ.get("TUCANO_CVM_PASSWORD", "senha-teste")
    token = os.environ.get("TUCANO_CVM_TOKEN", "token-teste")

    with TestClient(app) as client:
        resposta = client.post("/auth/login", json={"username": username, "password": password})

    assert resposta.status_code == 200
    assert resposta.json() == {"access_token": token, "token_type": "bearer"}


def test_login_rejeita_credenciais_invalidas() -> None:
    with TestClient(app) as client:
        resposta = client.post("/auth/login", json={"username": "invalido", "password": "errada"})

    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Usuario ou senha invalidos."


def test_endpoint_com_token_obtido_no_login(client: TestClient) -> None:
    username = os.environ.get("TUCANO_CVM_USERNAME", "frontend-teste")
    password = os.environ.get("TUCANO_CVM_PASSWORD", "senha-teste")

    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200

    token = login.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    resposta = client.get("/admin/sincronizacoes")
    assert resposta.status_code != 401

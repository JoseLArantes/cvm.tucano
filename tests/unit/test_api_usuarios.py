from typing import cast

from fastapi.testclient import TestClient


def _login(client: TestClient, username: str, password: str) -> str:
    resposta = client.post("/auth/login", json={"username": username, "password": password})
    assert resposta.status_code == 200
    return cast(str, resposta.json()["access_token"])


def test_crud_usuarios_com_token_sistema(client: TestClient) -> None:
    criado = client.post(
        "/usuarios",
        json={
            "username": "analista",
            "password": "senha-segura",
            "nome": "Analista",
            "is_admin": False,
            "pode_operar_materializacao": True,
            "ativo": True,
        },
    )
    assert criado.status_code == 201
    usuario_id = criado.json()["id"]
    assert "senha_hash" not in criado.json()

    listado = client.get("/usuarios")
    assert listado.status_code == 200
    assert listado.json()["paginacao"]["total"] == 1

    obtido = client.get(f"/usuarios/{usuario_id}")
    assert obtido.status_code == 200
    assert obtido.json()["username"] == "analista"
    assert obtido.json()["pode_operar_materializacao"] is True

    atualizado = client.patch(
        f"/usuarios/{usuario_id}",
        json={"nome": "Analista CVM", "ativo": False, "pode_operar_materializacao": False},
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["nome"] == "Analista CVM"
    assert atualizado.json()["ativo"] is False
    assert atualizado.json()["pode_operar_materializacao"] is False

    excluido = client.delete(f"/usuarios/{usuario_id}")
    assert excluido.status_code == 204


def test_usuario_admin_pode_gerenciar_usuarios(client: TestClient) -> None:
    admin = client.post(
        "/usuarios",
        json={"username": "admin", "password": "senha-admin", "nome": "Admin", "is_admin": True, "ativo": True},
    )
    assert admin.status_code == 201
    token = _login(client, "admin", "senha-admin")
    client.headers["Authorization"] = f"Bearer {token}"

    resposta = client.post(
        "/usuarios",
        json={
            "username": "operador",
            "password": "senha-operador",
            "nome": "Operador",
            "ativo": True,
            "pode_operar_materializacao": True,
        },
    )

    assert resposta.status_code == 201
    assert resposta.json()["username"] == "operador"
    assert resposta.json()["pode_operar_materializacao"] is True


def test_usuario_sem_admin_le_api_mas_nao_gerencia_usuarios(client: TestClient) -> None:
    criado = client.post(
        "/usuarios",
        json={"username": "leitor", "password": "senha-leitor", "nome": "Leitor", "ativo": True},
    )
    assert criado.status_code == 201
    token = _login(client, "leitor", "senha-leitor")
    client.headers["Authorization"] = f"Bearer {token}"

    companhias = client.get("/companhias")
    usuarios = client.get("/usuarios")

    assert companhias.status_code == 200
    assert usuarios.status_code == 403


def test_token_de_usuario_inativo_e_rejeitado(client: TestClient) -> None:
    criado = client.post(
        "/usuarios",
        json={"username": "leitor", "password": "senha-leitor", "nome": "Leitor", "ativo": True},
    )
    assert criado.status_code == 201
    token = _login(client, "leitor", "senha-leitor")

    client.headers["Authorization"] = "Bearer token-teste"
    assert client.patch(f"/usuarios/{criado.json()['id']}", json={"ativo": False}).status_code == 200

    client.headers["Authorization"] = f"Bearer {token}"
    resposta = client.get("/companhias")

    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Token de acesso invalido."


def test_rejeita_username_duplicado(client: TestClient) -> None:
    payload = {"username": "duplicado", "password": "senha-segura", "nome": "Duplicado"}
    assert client.post("/usuarios", json=payload).status_code == 201

    resposta = client.post("/usuarios", json=payload)

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Username ja cadastrado."


def test_nao_remove_ultimo_admin_ativo(client: TestClient) -> None:
    criado = client.post(
        "/usuarios",
        json={"username": "admin", "password": "senha-admin", "nome": "Admin", "is_admin": True, "ativo": True},
    )
    assert criado.status_code == 201

    resposta = client.delete(f"/usuarios/{criado.json()['id']}")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Nao e permitido remover o ultimo admin ativo."

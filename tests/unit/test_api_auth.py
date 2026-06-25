from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth import gerar_hash_senha
from app.main import app
from app.models.usuario import Usuario


def _criar_usuario(
    db_session: Session,
    username: str = "frontend-teste",
    password: str = "senha-teste",
    is_admin: bool = False,
    pode_operar_materializacao: bool = False,
    ativo: bool = True,
) -> Usuario:
    usuario = Usuario(
        username=username,
        nome="Usuario Teste",
        senha_hash=gerar_hash_senha(password),
        is_admin=is_admin,
        pode_operar_materializacao=pode_operar_materializacao,
        ativo=ativo,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def test_endpoints_exigem_token() -> None:
    with TestClient(app) as client:
        resposta = client.get("/ingestion/sincronizacoes")
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Token de acesso invalido."


def test_healthcheck_nao_exige_token() -> None:
    with TestClient(app) as client:
        resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_login_retorna_token_com_credenciais_validas(client: TestClient, db_session: Session) -> None:
    _criar_usuario(db_session)

    resposta = client.post("/auth/login", json={"username": "frontend-teste", "password": "senha-teste"})

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["access_token"].startswith("tucano.v1.")
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 28800


def test_login_rejeita_credenciais_invalidas(client: TestClient, db_session: Session) -> None:
    _criar_usuario(db_session)

    resposta = client.post("/auth/login", json={"username": "frontend-teste", "password": "senha-errada"})

    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Usuario ou senha invalidos."


def test_login_rejeita_usuario_inativo(client: TestClient, db_session: Session) -> None:
    _criar_usuario(db_session, ativo=False)

    resposta = client.post("/auth/login", json={"username": "frontend-teste", "password": "senha-teste"})

    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Usuario ou senha invalidos."


def test_endpoint_com_token_obtido_no_login(client: TestClient, db_session: Session) -> None:
    _criar_usuario(db_session)

    login = client.post("/auth/login", json={"username": "frontend-teste", "password": "senha-teste"})
    assert login.status_code == 200

    token = login.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    resposta = client.get("/companhias")
    assert resposta.status_code == 200


def test_me_retorna_usuario_logado(client: TestClient, db_session: Session) -> None:
    usuario = _criar_usuario(db_session)
    login = client.post("/auth/login", json={"username": "frontend-teste", "password": "senha-teste"})
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    resposta = client.get("/auth/me")

    assert resposta.status_code == 200
    assert resposta.json()["id"] == str(usuario.id)


def test_me_retorna_permissao_operacional_materializacao(client: TestClient, db_session: Session) -> None:
    _criar_usuario(db_session, pode_operar_materializacao=True)
    login = client.post("/auth/login", json={"username": "frontend-teste", "password": "senha-teste"})
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    resposta = client.get("/auth/me")

    assert resposta.status_code == 200
    assert resposta.json()["pode_operar_materializacao"] is True

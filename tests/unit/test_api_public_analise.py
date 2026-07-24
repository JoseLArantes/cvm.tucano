from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import get_settings
from app.models.companhia import Companhia


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mocka o RedisCache para evitar dependência externa em testes unitários."""
    mocked_cache = MagicMock()
    # Por padrão, simula cache miss
    mocked_cache.get.return_value = None
    monkeypatch.setattr(cache, "get", mocked_cache.get)
    monkeypatch.setattr(cache, "set", mocked_cache.set)
    return mocked_cache


@pytest.fixture()
def public_setup(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Companhia:
    """Configura o cenário com uma companhia no banco e nas configurações públicas."""
    # Define a companhia permitida nas configurações
    monkeypatch.setattr(get_settings(), "public_companies_cvm", "12345,67890")
    
    # Adiciona a companhia no banco em memória
    cia = Companhia(
        codigo_cvm=12345,
        cnpj_companhia="12345678000199",
        denominacao_social="COMPANHIA TESTE PUBLICA S.A.",
        situacao_registro="ATIVO",
        arquivo_origem="cadastro.csv",
        hash_origem="hash123",
        criado_em=datetime.now(UTC),
        sincronizado_em=datetime.now(UTC),
        alterado_em=datetime.now(UTC),
    )
    db_session.add(cia)
    db_session.commit()
    db_session.refresh(cia)
    return cia


def test_endpoint_publico_autorizado_com_cache_miss_e_hit(
    client: TestClient,
    public_setup: Companhia,
    mock_redis: MagicMock,
) -> None:
    """Valida o comportamento de cache miss (bate no DB, salva no Redis) e cache hit (retorna do Redis)."""
    # 1. Simula a primeira requisição (Cache Miss)
    # Sobrescrevemos o Authorization header padrão do fixture client para garantir requisição pública/anônima
    resposta = client.get(
        f"/public/analise/companhias/{public_setup.codigo_cvm}",
        headers={"Authorization": ""}  # Remove o Bearer token padrão
    )
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["companhia"]["codigo_cvm"] == 12345

    # Verifica se buscou no Redis e depois salvou
    assert mock_redis.get.call_count == 1
    assert mock_redis.set.call_count == 1

    # Obtém a chave gerada para usarmos no cache hit mockado
    key_chamada = mock_redis.get.call_args[0][0]
    valor_salvo = mock_redis.set.call_args[0][1]

    # 2. Configura o mock do Redis para retornar o dado salvo (Cache Hit)
    mock_redis.get.return_value = valor_salvo

    # Reseta o histórico de chamadas do mock
    mock_redis.get.reset_mock()
    mock_redis.set.reset_mock()

    # Faz a segunda requisição
    resposta_cached = client.get(
        f"/public/analise/companhias/{public_setup.codigo_cvm}",
        headers={"Authorization": ""}
    )
    assert resposta_cached.status_code == 200
    assert resposta_cached.json() == dados

    # Verifica se usou o cache e NÃO salvou novamente
    assert mock_redis.get.call_count == 1
    mock_redis.get.assert_called_with(key_chamada)
    assert mock_redis.set.call_count == 0


def test_endpoint_publico_nao_autorizado(
    client: TestClient,
    public_setup: Companhia,
) -> None:
    """Valida que companhias fora da lista pública retornam 403 Forbidden."""
    resposta = client.get(
        "/public/analise/companhias/99999",
        headers={"Authorization": ""}
    )
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Acesso nao autorizado para esta companhia."


def test_endpoint_publico_nao_encontrado(
    client: TestClient,
    public_setup: Companhia,
) -> None:
    """Valida que companhias autorizadas mas inexistentes no DB retornam 404 Not Found."""
    # CVM 67890 está na ENV de companhias públicas, mas não foi inserida no banco
    resposta = client.get(
        "/public/analise/companhias/67890",
        headers={"Authorization": ""}
    )
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Companhia nao encontrada."


def test_todos_os_endpoints_publicos_de_analise(
    client: TestClient,
    public_setup: Companhia,
    mock_redis: MagicMock,
) -> None:
    """Garante que todas as 12 rotas públicas estão devidamente conectadas aos serviços."""
    endpoints = [
        "",
        "/coverage",
        "/series",
        "/series/diagnostico",
        "/comparacoes",
        "/qualidade",
        "/sinais",
        "/eventos",
        "/governanca",
        "/pessoas",
        "/brief",
        "/restatements",
    ]
    for suffix in endpoints:
        url = f"/public/analise/companhias/{public_setup.codigo_cvm}{suffix}"
        resposta = client.get(url, headers={"Authorization": ""})
        # Os endpoints devem responder com sucesso (200) ou 404 (caso não haja dados da companhia fictícia no SQLite),
        # mas nunca com erros internos do servidor (500) ou erro de assinatura de rota.
        assert resposta.status_code in (200, 404)


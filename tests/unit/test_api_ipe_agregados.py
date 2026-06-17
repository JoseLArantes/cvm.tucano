import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.ipe import IpeDocumento


def _seed_ipe_agregados(db: Session, cia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    docs = [
        IpeDocumento(
            companhia_id=cia_id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2025, 1, 1),
            categoria="Fato Relevante",
            tipo="Tipo A",
            especie="Especie A",
            data_entrega=date(2025, 1, 15),
            versao=1,
            arquivo_origem="ipe.csv",
            hash_origem="hash",
            criado_em=agora, sincronizado_em=agora, alterado_em=agora
        ),
        IpeDocumento(
            companhia_id=cia_id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2025, 5, 1),
            categoria="Fato Relevante",
            tipo="Tipo B",
            especie="Especie A",
            data_entrega=date(2025, 5, 20),
            versao=1,
            arquivo_origem="ipe.csv",
            hash_origem="hash",
            criado_em=agora, sincronizado_em=agora, alterado_em=agora
        ),
        IpeDocumento(
            companhia_id=cia_id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2024, 12, 1),
            categoria="Comunicado",
            tipo="Tipo A",
            especie="Especie B",
            data_entrega=date(2024, 12, 5),
            versao=1,
            arquivo_origem="ipe.csv",
            hash_origem="hash",
            criado_em=agora, sincronizado_em=agora, alterado_em=agora
        )
    ]
    for d in docs:
        db.add(d)
    db.commit()


def test_ipe_documentos_agregados(client: TestClient, db_session: Session) -> None:
    cia = Companhia(
        cnpj_companhia="00000000000191",
        codigo_cvm=1023,
        denominacao_social="Banco do Brasil S.A.",
        situacao_registro="ATIVO",
        arquivo_origem="cad_cia_aberta.csv",
        hash_origem="abc",
        criado_em=datetime.now(UTC),
        sincronizado_em=datetime.now(UTC),
        alterado_em=datetime.now(UTC)
    )
    db_session.add(cia)
    db_session.commit()

    _seed_ipe_agregados(db_session, cia.id)

    # Test grouping by ano, categoria
    resp = client.get("/ipe/documentos/agregados?codigo_cvm=1023&agrupar_por=ano,categoria")
    assert resp.status_code == 200
    dados = resp.json()["dados"]
    assert len(dados) >= 2
    # 2025 Fato Relevante should have total = 2
    match_2025 = next((x for x in dados if x["ano"] == 2025 and x["categoria"] == "Fato Relevante"), None)
    assert match_2025 is not None
    assert match_2025["total"] == 2

    # Test grouping by tipo
    resp_tipo = client.get("/ipe/documentos/agregados?codigo_cvm=1023&agrupar_por=tipo")
    assert resp_tipo.status_code == 200
    dados_tipo = resp_tipo.json()["dados"]
    match_tipo_a = next((x for x in dados_tipo if x["tipo"] == "Tipo A"), None)
    assert match_tipo_a is not None
    assert match_tipo_a["total"] == 2

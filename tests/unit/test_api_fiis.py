import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.fii import FiiInformeAtivoPassivo, FiiInformeComplemento, FiiInformeGeral
from app.models.sincronizacao import ExecucaoSincronizacao


def _execution(db: Session) -> uuid.UUID:
    execution = ExecucaoSincronizacao(
        tipo_execucao="arquivo_zip",
        tipo_fonte="fii",
        ano=2026,
        id_tarefa=str(uuid.uuid4()),
        arquivo="inf_mensal_fii_2026.zip",
        url="https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_2026.zip",
        status="sucesso",
    )
    db.add(execution)
    db.flush()
    return execution.id


def _general(execution_id: uuid.UUID, *, cnpj: str, tipo: str, version: int, current: bool = True) -> FiiInformeGeral:
    return FiiInformeGeral(
        cnpj=cnpj,
        tipo=tipo,
        data_referencia=date(2026, 1, 1),
        versao=version,
        nome="FII Exemplo",
        codigo_isin="BRFIICTF0001",
        segmento_atuacao="Logistica",
        dados={"Data_Entrega": "2026-02-15", "Nome_Fundo_Classe": "FII Exemplo"},
        linha_origem=2,
        hash_origem=f"hash-{tipo}-{version}",
        arquivo_origem="inf_mensal_fii_geral_2026.csv",
        ano_origem=2026,
        execucao_sincronizacao_id=execution_id,
        consta_no_snapshot_atual=current,
    )


def test_fii_api_filters_versions_and_ambiguous_sections(client: TestClient, db_session: Session) -> None:
    execution_id = _execution(db_session)
    db_session.add_all([
        _general(execution_id, cnpj="A1B2C3D4E5F600", tipo="fundo", version=1, current=False),
        _general(execution_id, cnpj="A1B2C3D4E5F600", tipo="fundo", version=2),
        _general(execution_id, cnpj="A1B2C3D4E5F600", tipo="classe", version=2),
        _general(execution_id, cnpj="B2B2B2B2B2B200", tipo="fundo", version=1),
    ])
    db_session.flush()
    db_session.add_all([
        FiiInformeComplemento(
            cnpj="A1B2C3D4E5F600", tipo="fundo", data_referencia=date(2026, 1, 1), versao=1,
            status_atribuicao="disponivel", ocorrencias=1,
            dados={"Patrimonio_Liquido": "900000.00"}, linha_origem=2, hash_variante="old-complement",
            hash_origem="old-hash", arquivo_origem="inf_mensal_fii_complemento_2026.csv", ano_origem=2026,
            execucao_sincronizacao_id=execution_id, consta_no_snapshot_atual=False,
        ),
        FiiInformeComplemento(
            cnpj="B2B2B2B2B2B200", tipo="fundo", data_referencia=date(2026, 1, 1), versao=1,
            status_atribuicao="disponivel", ocorrencias=1,
            dados={
                "Valor_Ativo": "1500000.000", "Patrimonio_Liquido": "123456.70",
                "Valor_Patrimonial_Cotas": "10.50", "Total_Numero_Cotistas": 25,
                "Percentual_Dividend_Yield_Mes": "0.0035",
            }, linha_origem=2, hash_variante="single-complement",
            hash_origem="single-hash", arquivo_origem="inf_mensal_fii_complemento_2026.csv", ano_origem=2026,
            execucao_sincronizacao_id=execution_id, consta_no_snapshot_atual=True,
        ),
        FiiInformeComplemento(
            cnpj="A1B2C3D4E5F600", tipo=None, data_referencia=date(2026, 1, 1), versao=2,
            status_atribuicao="ambiguo", ocorrencias=1,
            dados={"Patrimonio_Liquido": "1000000.25"}, linha_origem=3, hash_variante="variant-a",
            hash_origem="hash-a", arquivo_origem="inf_mensal_fii_complemento_2026.csv", ano_origem=2026,
            execucao_sincronizacao_id=execution_id, consta_no_snapshot_atual=True,
        ),
        FiiInformeComplemento(
            cnpj="A1B2C3D4E5F600", tipo=None, data_referencia=date(2026, 1, 1), versao=2,
            status_atribuicao="ambiguo", ocorrencias=1,
            dados={"Patrimonio_Liquido": "1000000.50"}, linha_origem=4, hash_variante="variant-b",
            hash_origem="hash-b", arquivo_origem="inf_mensal_fii_complemento_2026.csv", ano_origem=2026,
            execucao_sincronizacao_id=execution_id, consta_no_snapshot_atual=True,
        ),
        FiiInformeAtivoPassivo(
            cnpj="A1B2C3D4E5F600", tipo="fundo", data_referencia=date(2026, 1, 1), versao=2,
            status_atribuicao="disponivel", ocorrencias=1, dados={"Total_Passivo": "125.5"},
            linha_origem=3, hash_variante="asset-a", hash_origem="asset-hash",
            arquivo_origem="inf_mensal_fii_ativo_passivo_2026.csv", ano_origem=2026,
            execucao_sincronizacao_id=execution_id, consta_no_snapshot_atual=True,
        ),
    ])
    db_session.commit()

    listed = client.get("/fiis?cnpj=A1B2C3D4E5F600")
    assert listed.status_code == 200
    assert {item["tipo"] for item in listed.json()["dados"]} == {"fundo", "classe"}
    assert listed.json()["paginacao"]["total"] == 2
    single = client.get("/fiis?cnpj=B2B2B2B2B2B200").json()["dados"][0]
    assert single["patrimonio_liquido_brl"] == "123456.7"
    assert single["valor_ativo_brl"] == "1500000"
    assert single["cotistas_total"] == 25

    report = client.get("/fiis/A1B2C3D4E5F600/fundo/informes/2026-01")
    assert report.status_code == 200
    assert report.json()["versao"] == 2
    assert report.json()["complemento"]["status"] == "ambiguo"
    assert report.json()["complemento"]["dados"] is None
    assert len(report.json()["complemento"]["variantes"]) == 2
    assert report.json()["ativo_passivo"]["status"] == "disponivel"

    historical = client.get("/fiis/A1B2C3D4E5F600/fundo/informes?competencia_inicio=2026-01&todas_versoes=true")
    assert historical.status_code == 200
    assert [item["versao"] for item in historical.json()["dados"]] == [2, 1]
    assert historical.json()["dados"][1]["consta_no_snapshot_atual"] is False
    old_report = client.get("/fiis/A1B2C3D4E5F600/fundo/informes/2026-01?versao=1").json()
    assert old_report["consta_no_snapshot_atual"] is False
    assert old_report["complemento"]["status"] == "disponivel"
    assert old_report["complemento"]["dados"]["Patrimonio_Liquido"] == "900000.00"
    assert old_report["complemento"]["unidades"]["Patrimonio_Liquido"] == "BRL"
    assert client.get("/fiis/12.345.678-0001-90/fundo").status_code == 422
    assert client.get("/fiis?cnpj=12.345.678/0001-90").status_code == 200
    assert client.get("/fiis/A1B2C3D4E5F600/fundo/informes/2026-13").status_code == 422


def test_fii_openapi_lists_authenticated_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/fiis" in schema["paths"]
    assert "/fiis/{cnpj}/{tipo}/informes/{competencia}" in schema["paths"]
    assert "obterInformeFii" in schema["paths"]["/fiis/{cnpj}/{tipo}/informes/{competencia}"]["get"]["operationId"]
    assert "/ingestion/sincronizacoes/fii/{ano}" in schema["paths"]
    assert client.get("/fiis", headers={"Authorization": ""}).status_code == 401

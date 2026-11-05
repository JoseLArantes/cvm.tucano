from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import financeiro, fre, identidade, ingestion, sincronizacao, usuario, vlmo  # noqa: F401
from app.models.companhia import Companhia
from app.models.fre import FreRelacaoFamiliar
from app.models.ingestion import IngestionFile, IngestionRun, QuarantineItem
from app.models.sincronizacao import ExecucaoSincronizacao, RegistroQuarentena
from app.models.vlmo import VlmoDocumento
from app.services.ingestion.cadastro import normalizar_linha_cadastro_estrangeira, promover_registros_cadastro
from app.services.ingestion.fre import normalizar_fre_row
from app.services.ingestion.quarantine import create_quarantine_item
from app.services.ingestion.replay import auto_repair_and_replay_quarantine
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload
from app.services.ingestion.validation import ValidationResult, write_validation_result
from app.services.ingestion.vlmo import _promote_vlmo_row, normalizar_vlmo_row
from app.services.normalizacao import normalizar_data


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def _run_and_file(
    session: Session, *, tipo_fonte: str = "fre", ano: int = 2023
) -> tuple[ExecucaoSincronizacao, IngestionRun, IngestionFile]:
    execucao = ExecucaoSincronizacao(
        tipo_fonte=tipo_fonte,
        ano=ano,
        arquivo=f"{tipo_fonte}.zip",
        url="https://example.test",
        status="em_execucao",
    )
    session.add(execucao)
    session.flush()
    run = create_run(
        session,
        tipo_fonte=tipo_fonte,
        ano=ano,
        execucao_sincronizacao_id=execucao.id,
    )
    ingestion_file = register_file(
        session,
        ingestion_run=run,
        source_url="https://example.test/file.zip",
        source_filename="file.zip",
        payload=b"fake",
        is_zip=True,
    )
    return execucao, run, ingestion_file


def _empresa(session: Session) -> Companhia:
    registro = normalizar_linha_cadastro_estrangeira(
        {
            "CNPJ": "07.857.093/0001-14",
            "DENOM_SOCIAL": "AURA MINERALS INC.",
            "DENOM_COMERC": "AURA MINERALS INC.",
            "PAIS_ORIGEM": "EXTERIOR",
            "DT_REG": "2020-01-01",
            "DT_CONST": "2000-01-01",
            "DT_CANCEL": "",
            "MOTIVO_CANCEL": "",
            "SIT": "ATIVO",
            "DT_INI_SIT": "2020-01-01",
            "CD_CVM": "80187",
            "SETOR_ATIV": "Mineracao",
        },
        linha_origem=2,
    )
    assert registro.data is not None
    promover_registros_cadastro(session, [registro.data])
    session.flush()
    return session.query(Companhia).filter(Companhia.codigo_cvm == 80187).one()


def test_normalizar_data_sentinelas_e_resiliencia() -> None:
    # Sentinelas devem virar None
    assert normalizar_data("N/A") is None
    assert normalizar_data("n/a") is None
    assert normalizar_data("-") is None
    assert normalizar_data("ND") is None
    assert normalizar_data("N/D") is None
    assert normalizar_data("0000-00-00") is None
    assert normalizar_data("SEM DATA") is None

    # Formatos validos
    assert normalizar_data("2023-05-10") == date(2023, 5, 10)
    assert normalizar_data("2023-05-10 14:30:00") == date(2023, 5, 10)
    assert normalizar_data("2023-05-10T14:30:00") == date(2023, 5, 10)
    assert normalizar_data("10/05/2023") == date(2023, 5, 10)


def test_fre_relacao_familiar_truncamento_texto_gigante() -> None:
    texto_gigante = "DIRETOR PRESIDENTE " + ("X" * 10000)
    linha_raw = {
        "CNPJ_Companhia": "07.857.093/0001-14",
        "Data_Referencia": "2022-12-31",
        "Versao": "1",
        "ID_Documento": "100",
        "Nome_Administrador": "JOAO DA SILVA",
        "Nome_Pessoa_Relacionada": "MARIA DA SILVA",
        "Cargo_Pessoa_Relacionada": texto_gigante,
        "Cargo_Administrador": "DIRETOR",
        "Tipo_Parentesco": "CONJUGE",
        "Observacao": "Obs inicial",
    }
    row_kind, dados = normalizar_fre_row(
        tipo="relacao_familiar",
        arquivo_origem="fre_cia_aberta_relacao_familiar_2022.csv",
        ano_origem=2022,
        linha_origem=1,
        linha=linha_raw,
    )
    assert row_kind == "fre_relacao_familiar"
    # O cargo deve ter sido truncado a no maximo 500 caracteres
    assert len(dados["cargo_Pessoa_relacionada"]) == 500
    assert dados["cargo_Pessoa_relacionada"].startswith("DIRETOR PRESIDENTE")
    # O texto original deve ter sido anexado a observacao para evitar perda de dados
    assert "Cargo_Pessoa_Relacionada original" in dados["observacao"]
    assert texto_gigante in dados["observacao"]


def test_vlmo_documento_conflito_chave_alternativa() -> None:
    session = _session()
    try:
        empresa = _empresa(session)
        execucao, run, ingestion_file = _run_and_file(session, tipo_fonte="vlmo", ano=2023)

        payload1 = (
            b"CNPJ_Companhia;Codigo_CVM;Data_Referencia;Categoria;Tipo;Data_Entrega;Tipo_Apresentacao;Motivo_Reapresentacao;Protocolo_Entrega;Versao;Link_Download\n"
            b"07.857.093/0001-14;80187;2023-05-01;CAT_TESTE;TIPO_TESTE;2024-01-10;APRESENTACAO;;PROTOCOLO_111;1;http://teste.com/1\n"
        )
        member1, rows1 = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=payload1,
            member_name="vlmo_cia_aberta_2023.csv",
            arquivo_origem="vlmo_cia_aberta_2023.csv",
            ano_origem=2023,
            row_kind="vlmo_documento",
        )
        row1 = rows1[0]
        row_kind1, dados_p1 = normalizar_vlmo_row(
            arquivo_origem="vlmo_cia_aberta_2023.csv",
            ano_origem=2023,
            linha_origem=1,
            linha=row1.raw_data,
        )
        dados_p1["companhia_id"] = empresa.id

        contadores1 = {"inseridos": 0, "atualizados": 0, "inalterados": 0}
        _promote_vlmo_row(session, row_kind=row_kind1, row=row1, dados=dados_p1, execucao_id=execucao.id, contadores=contadores1)
        session.commit()

        assert contadores1["inseridos"] == 1
        docs = session.query(VlmoDocumento).all()
        assert len(docs) == 1
        assert docs[0].protocolo_entrega == "PROTOCOLO_111"

        # Segunda linha: mesma chave alternativa, mas novo protocolo de entrega
        payload2 = (
            b"CNPJ_Companhia;Codigo_CVM;Data_Referencia;Categoria;Tipo;Data_Entrega;Tipo_Apresentacao;Motivo_Reapresentacao;Protocolo_Entrega;Versao;Link_Download\n"
            b"07.857.093/0001-14;80187;2023-05-01;CAT_TESTE;TIPO_TESTE;2024-01-10;APRESENTACAO;;PROTOCOLO_222;1;http://teste.com/2\n"
        )
        member2, rows2 = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=payload2,
            member_name="vlmo_cia_aberta_2023.csv",
            arquivo_origem="vlmo_cia_aberta_2023.csv",
            ano_origem=2023,
            row_kind="vlmo_documento",
        )
        row2 = rows2[0]
        row_kind2, dados_p2 = normalizar_vlmo_row(
            arquivo_origem="vlmo_cia_aberta_2023.csv",
            ano_origem=2023,
            linha_origem=2,
            linha=row2.raw_data,
        )
        dados_p2["companhia_id"] = empresa.id

        contadores2 = {"inseridos": 0, "atualizados": 0, "inalterados": 0}
        _promote_vlmo_row(session, row_kind=row_kind2, row=row2, dados=dados_p2, execucao_id=execucao.id, contadores=contadores2)
        session.commit()

        # Deve atualizar o documento existente sem violar a constraint alternativa
        assert contadores2["atualizados"] == 1
        docs_finais = session.query(VlmoDocumento).all()
        assert len(docs_finais) == 1
        assert docs_finais[0].protocolo_entrega == "PROTOCOLO_222"
        assert docs_finais[0].link_download == "http://teste.com/2"
    finally:
        session.close()


def test_auto_repair_and_replay_quarantine() -> None:
    session = _session()
    try:
        _empresa(session)
        execucao, run, ingestion_file = _run_and_file(session, tipo_fonte="fre", ano=2023)

        payload_csv = (
            b"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Administrador;CPF_Administrador;Nome_Emissor;CNPJ_Emissor;Cargo_Administrador;Nome_Pessoa_Relacionada;CPF_Pessoa_Relacionada;Nome_Emissor_Pessoa_Relacionada;CNPJ_Emissor_Pessoa_Relacionada;Cargo_Pessoa_Relacionada;Tipo_Parentesco;Observacao\n"
            b"07.857.093/0001-14;2023-12-31;1;999;AURA;CARLOS;12345678901;AURA;07.857.093/0001-14;DIRETOR;ANA;98765432100;AURA;07.857.093/0001-14;GERENTE;CONJUGE;N/A\n"
        )
        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=payload_csv,
            member_name="fre_cia_aberta_relacao_familiar_2023.csv",
            arquivo_origem="fre_cia_aberta_relacao_familiar_2023.csv",
            ano_origem=2023,
            row_kind="fre_relacao_familiar",
        )
        row = rows[0]
        result = ValidationResult(
            status="invalid",
            reason_code="normalizacao_invalida",
            severity="error",
            details={"error": "Invalid isoformat string: 'N/A'"},
            repairable=True,
        )
        write_validation_result(session, ingestion_row=row, result=result)
        q_item = create_quarantine_item(session, ingestion_row=row, result=result, execucao_sincronizacao_id=execucao.id)
        session.commit()

        assert q_item.status == "pendente"
        assert session.query(RegistroQuarentena).count() == 1

        # Executa auto_repair_and_replay_quarantine
        relatorio = auto_repair_and_replay_quarantine(session)

        assert relatorio["status"] == "completed"
        assert relatorio["candidatos"] == 1
        assert relatorio["resolvidos"] == 1
        assert relatorio["falhados"] == 0

        # Verifica se o item foi marcado como resolvido_auto
        q_atualizado = session.get(QuarantineItem, q_item.id)
        assert q_atualizado is not None
        assert q_atualizado.status == "resolvido_auto"
        assert q_atualizado.resolvido_por == "auto_repair"

        # Verifica se a quarentena legada foi limpa
        assert session.query(RegistroQuarentena).count() == 0

        # Verifica se a linha foi promovida para a tabela final
        assert session.query(FreRelacaoFamiliar).count() == 1
    finally:
        session.close()


from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.fre import FreAuditor
from app.models.ingestion import IngestionAttempt, IngestionFile, IngestionRun, QuarantineItem
from app.models.sincronizacao import ExecucaoSincronizacao, RegistroQuarentena
from app.services.ingestion.cadastro import normalizar_linha_cadastro_estrangeira, promover_registros_cadastro
from app.services.ingestion.quarantine import create_quarantine_item
from app.services.ingestion.repair_rules import create_or_update_repair_rule
from app.services.ingestion.replay import replay_ingestion_row
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload
from app.services.ingestion.validation import ValidationResult, write_validation_result


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
    session: Session, *, tipo_fonte: str = "fre", ano: int = 2025
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


def _foreign_company(session: Session) -> Companhia:
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
    empresa = session.query(Companhia).filter(Companhia.codigo_cvm == 80187).one()
    return empresa


def test_create_quarantine_item_creates_v2_and_legacy_records() -> None:
    session = _session()
    try:
        execucao, run, ingestion_file = _run_and_file(session)
        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=b"CNPJ_CIA;DT_REFER;VERSAO;ID_DOC\n11.111.111/0001-11;2025-12-31;1;10\n",
            member_name="dfp_cia_aberta_2025.csv",
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
            row_kind="dfp_documento",
        )
        row = rows[0]
        result = ValidationResult(
            status="invalid",
            reason_code="companhia_nao_encontrada",
            severity="error",
            details={"foo": "bar"},
            repairable=True,
        )
        write_validation_result(session, ingestion_row=row, result=result, normalized_data={"id_documento": 10})
        create_quarantine_item(session, ingestion_row=row, result=result, execucao_sincronizacao_id=execucao.id)
        session.commit()

        assert session.query(QuarantineItem).count() == 1
        assert session.query(RegistroQuarentena).count() == 1
    finally:
        session.close()


def test_replay_row_resolves_after_foreign_identity_added() -> None:
    session = _session()
    try:
        execucao, run, ingestion_file = _run_and_file(session, tipo_fonte="dfp")
        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=(
                b"CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                b"07.857.093/0001-14;2025-12-31;1;AURA MINERALS INC.;80187;DFP;123;2026-01-01;http://doc\n"
            ),
            member_name="dfp_cia_aberta_2025.csv",
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
            row_kind="dfp_documento",
        )
        row = rows[0]
        result = ValidationResult(
            status="invalid",
            reason_code="companhia_nao_encontrada",
            severity="error",
            details={},
            repairable=True,
        )
        write_validation_result(session, ingestion_row=row, result=result)
        create_quarantine_item(session, ingestion_row=row, result=result, execucao_sincronizacao_id=execucao.id)
        session.commit()

        _foreign_company(session)
        session.commit()

        replay_result = replay_ingestion_row(session, row_id=row.id)
        session.refresh(row)
        quarantine = session.query(QuarantineItem).one()

        assert replay_result["status"] == "sucesso"
        assert row.resolved_companhia_id is not None
        assert quarantine.status == "resolvido_auto"
    finally:
        session.close()


def test_replay_row_uses_manual_repair_rule() -> None:
    session = _session()
    try:
        execucao, run, ingestion_file = _run_and_file(session, tipo_fonte="fre")
        companhia = _foreign_company(session)
        session.commit()
        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=(
                b"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;Razao_Apresentada\n"
                b";2025-12-31;1;123;EMPRESA FINANCEIRA;1;AUDITOR X;12345678900;"
                b"10.830.108/0001-65;100;ORIGEM;2020-01-01;;2020-01-01;SERVICO;1000,00;JUST;RAZAO\n"
            ),
            member_name="fre_cia_aberta_auditor_2025.csv",
            arquivo_origem="fre_cia_aberta_auditor_2025.csv",
            ano_origem=2025,
            row_kind="fre_auditor",
        )
        row = rows[0]
        result = ValidationResult(
            status="invalid",
            reason_code="companhia_nao_encontrada",
            severity="error",
            details={},
            repairable=True,
        )
        write_validation_result(session, ingestion_row=row, result=result)
        create_quarantine_item(session, ingestion_row=row, result=result, execucao_sincronizacao_id=execucao.id)
        create_or_update_repair_rule(
            session,
            rule_type="identity_exact",
            match_payload={
                "tipo_formulario": "FRE",
                "id_documento": 123,
                "versao": 1,
                "data_referencia": "2025-12-31",
                "nome_emissor_chave": "EMPRESA FINANCEIRA",
            },
            action_payload={"companhia_id": str(companhia.id)},
        )
        session.commit()

        replay_result = replay_ingestion_row(session, row_id=row.id)

        assert replay_result["status"] == "sucesso"
        assert session.query(FreAuditor).count() == 1
    finally:
        session.close()


def test_replay_failure_increments_attempt_count() -> None:
    session = _session()
    try:
        execucao, run, ingestion_file = _run_and_file(session, tipo_fonte="fre")
        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=(
                b"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;Razao_Apresentada\n"
                b";2025-12-31;1;123;EMPRESA SEM REGRA;1;AUDITOR X;12345678900;"
                b"10.830.108/0001-65;100;ORIGEM;2020-01-01;;2020-01-01;SERVICO;1000,00;JUST;RAZAO\n"
            ),
            member_name="fre_cia_aberta_auditor_2025.csv",
            arquivo_origem="fre_cia_aberta_auditor_2025.csv",
            ano_origem=2025,
            row_kind="fre_auditor",
        )
        row = rows[0]
        result = ValidationResult(
            status="invalid",
            reason_code="companhia_nao_encontrada",
            severity="error",
            details={},
            repairable=True,
        )
        write_validation_result(session, ingestion_row=row, result=result)
        create_quarantine_item(session, ingestion_row=row, result=result, execucao_sincronizacao_id=execucao.id)
        session.commit()

        replay_result = replay_ingestion_row(session, row_id=row.id)
        quarantine = session.query(QuarantineItem).one()
        attempts = session.query(IngestionAttempt).all()

        assert replay_result["status"] == "falha"
        assert quarantine.tentativas_reprocessamento == 1
        assert any(item.operation == "replay" for item in attempts)
    finally:
        session.close()

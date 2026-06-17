from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import companhia, financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.ingestion import IngestionRowEvent
from app.services.ingestion.quarantine import _normalizar_reason_code
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload
from app.services.ingestion.validation import (
    ValidationResult,
    build_duplicate_comparison_data,
    build_natural_key,
    classify_duplicate,
    invalid_result,
    update_member_schema_validation,
    validate_member_header,
    write_validation_result,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def _staged_row(session: Session) -> tuple[Any, Any]:
    run = create_run(session, tipo_fonte="dfp", ano=2025)
    ingestion_file = register_file(
        session,
        ingestion_run=run,
        source_url="https://example.test/dfp.zip",
        source_filename="dfp.zip",
        payload=b"fake",
        is_zip=True,
    )
    member, rows = stage_csv_payload(
        session,
        ingestion_run=run,
        ingestion_file=ingestion_file,
        payload=b"CNPJ_CIA;DT_REFER;VERSAO;ID_DOC\n08.773.135/0001-00;2025-12-31;1;10\n",
        member_name="dfp_cia_aberta_2025.csv",
        arquivo_origem="dfp_cia_aberta_2025.csv",
        ano_origem=2025,
        row_kind="dfp_documento",
    )
    return member, rows[0]


def test_validation_result_serializes_details_to_json() -> None:
    result = ValidationResult(
        status="invalid",
        reason_code="schema_inesperado",
        severity="error",
        details={"missing": ["ID_DOC"]},
        repairable=True,
    )

    payload = result.to_json_payload()

    assert payload["details"]["missing"] == ["ID_DOC"]
    assert payload["repairable"] is True


def test_validate_member_header_missing_required_column_returns_schema_inesperado() -> None:
    result = validate_member_header("dfp_documento", ["CNPJ_CIA", "DT_REFER", "VERSAO"])

    assert result.status == "invalid"
    assert result.reason_code == "schema_inesperado"
    assert result.repairable is True
    assert result.details["missing_required_columns"] == ["ID_DOC"]


def test_validate_member_header_detects_changed_fre_titular_schema() -> None:
    result = validate_member_header(
        "fre_titular_valor_mobiliario",
        [
            "CNPJ_Companhia",
            "Data_Referencia",
            "Versao",
            "ID_Documento",
            "Valor_Mobiliario",
            "Quantidade_Pessoa_Fisica",
            "Quantidade_Pessoa_Juridica",
            "Quantidade_Investidor",
        ],
    )

    assert result.status == "invalid"
    assert result.reason_code == "schema_inesperado"
    assert result.details["missing_required_columns"] == ["Classe_Valor_Mobiliario", "Nome_Titular"]


def test_build_natural_key_for_dfp_demonstracao_fre_auditor_and_cadastro() -> None:
    demonstracao = build_natural_key(
        "dfp_demonstracao",
        {
            "tipo_formulario": "DFP",
            "tipo_demonstracao": "BPA",
            "escopo_demonstracao": "CON",
            "cnpj_companhia": "08773135000100",
            "data_referencia": "2025-12-31",
            "versao": 1,
            "grupo_demonstracao": "Ativo",
            "ordem_exercicio": "ÚLTIMO",
            "data_inicio_exercicio": "2025-01-01",
            "data_fim_exercicio": "2025-12-31",
            "codigo_conta": "1.01",
            "coluna_df": "Reservas de Lucro",
        },
    )
    fre_auditor = build_natural_key(
        "fre_auditor",
        {
            "id_documento": 10,
            "versao": 1,
            "data_referencia": "2025-12-31",
            "cnpj_companhia": "07857093000114",
            "id_auditor": 3,
        },
    )
    cadastro = build_natural_key(
        "cadastro_registro_cvm",
        {
            "fonte_cadastro": "cad_cia_aberta",
            "cnpj_companhia": "08773135000100",
            "codigo_cvm": 25224,
            "hash_sem_mercado": "abc",
        },
    )

    assert demonstracao["codigo_conta"] == "1.01"
    assert demonstracao["coluna_df"] == "Reservas de Lucro"
    assert demonstracao["data_inicio_exercicio"] == "2025-01-01"
    assert fre_auditor["id_auditor"] == 3
    assert cadastro["hash_sem_mercado"] == "abc"


def test_classify_duplicate_ignores_exact_duplicate() -> None:
    seen_by_key: dict[str, dict[str, Any]] = {}
    natural_key = {"id_documento": 10, "versao": 1}
    normalized_data = {"id_documento": 10, "versao": 1, "valor": "A"}

    first = classify_duplicate(
        row_kind="fca_documento",
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data=normalized_data,
        seen_by_key=seen_by_key,
    )
    second = classify_duplicate(
        row_kind="fca_documento",
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data=normalized_data,
        seen_by_key=seen_by_key,
    )

    assert first.status == "valid"
    assert second.status == "ignored_duplicate"
    assert second.reason_code == "ignored_duplicate"


def test_classify_duplicate_accepts_conflict_as_update() -> None:
    seen_by_key: dict[str, dict[str, Any]] = {}
    natural_key = {"id_documento": 10, "versao": 1}

    classify_duplicate(
        row_kind="fca_documento",
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data={"id_documento": 10, "versao": 1, "valor": "A"},
        seen_by_key=seen_by_key,
    )
    conflict = classify_duplicate(
        row_kind="fca_documento",
        natural_key=natural_key,
        normalized_hash="hash-b",
        normalized_data={"id_documento": 10, "versao": 1, "valor": "B"},
        seen_by_key=seen_by_key,
    )

    assert conflict.status == "valid"
    assert conflict.details["duplicate_status"] == "updated"


def test_classify_duplicate_ignores_source_lineage_and_mutation_fields() -> None:
    seen_by_key: dict[str, dict[str, Any]] = {}
    natural_key = {"tipo_formulario": "DFP", "codigo_conta": "3.03"}
    first_row = {
        "tipo_formulario": "DFP",
        "codigo_conta": "3.03",
        "valor": "10",
        "linha_origem": 2960,
        "arquivo_origem": "dfp.csv",
    }
    second_row = {
        "tipo_formulario": "DFP",
        "codigo_conta": "3.03",
        "valor": "10",
        "linha_origem": 2961,
        "arquivo_origem": "dfp.csv",
        "companhia_id": "8f42b17e-51b5-4443-a9f0-faea0d7cda58",
    }

    classify_duplicate(
        row_kind="dfp_demonstracao",
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data=first_row,
        seen_by_key=seen_by_key,
    )
    result = classify_duplicate(
        row_kind="dfp_demonstracao",
        natural_key=natural_key,
        normalized_hash="hash-b",
        normalized_data=second_row,
        seen_by_key=seen_by_key,
    )

    assert build_duplicate_comparison_data(first_row) == build_duplicate_comparison_data(second_row)
    assert result.status == "ignored_duplicate"
    assert result.reason_code == "ignored_duplicate"


def test_classify_duplicate_financeiro_prefers_non_zero_over_zero_shadow() -> None:
    seen_by_key: dict[str, dict[str, Any]] = {}
    natural_key = {"tipo_formulario": "ITR", "codigo_conta": "5.04", "coluna_df": "Reservas"}

    first = classify_duplicate(
        row_kind="itr_demonstracao",
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data={"tipo_formulario": "ITR", "codigo_conta": "5.04", "coluna_df": "Reservas", "valor_conta": "-2.0000000000"},
        seen_by_key=seen_by_key,
    )
    second = classify_duplicate(
        row_kind="itr_demonstracao",
        natural_key=natural_key,
        normalized_hash="hash-b",
        normalized_data={"tipo_formulario": "ITR", "codigo_conta": "5.04", "coluna_df": "Reservas", "valor_conta": "0.0000000000"},
        seen_by_key=seen_by_key,
    )

    assert first.status == "valid"
    assert second.status == "ignored_duplicate"
    assert second.details["duplicate_status"] == "ignored_zero_shadow"


def test_write_validation_result_updates_row_and_event_and_member_schema() -> None:
    session = _session()
    try:
        member, row = _staged_row(session)
        schema_result = validate_member_header("dfp_documento", member.header)
        update_member_schema_validation(member, result=schema_result)

        result = ValidationResult(
            status="invalid",
            reason_code="schema_inesperado",
            severity="error",
            details={"missing": ["ID_DOC"]},
            repairable=True,
        )
        write_validation_result(
            session,
            ingestion_row=row,
            result=result,
            normalized_data={"tipo_formulario": "DFP", "id_documento": 10},
            natural_key={"tipo_formulario": "DFP", "id_documento": 10},
        )
        session.commit()
        session.refresh(row)
        session.refresh(member)

        assert row.validation_status == "invalid"
        assert row.validation_reason_code == "schema_inesperado"
        assert row.validation_details["details"]["missing"] == ["ID_DOC"]
        assert member.schema_status == "valid"
        event = session.query(IngestionRowEvent).one()
        assert event.event_type == "quarantined"
    finally:
        session.close()


_NEW_FRE_REQUIRED_HEADERS: dict[str, set[str]] = {
    "fre_capital_social_aumento": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Capital_Social",
    },
    "fre_capital_social_aumento_classe_acao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "ID_Capital_Social", "Tipo_Classe_Acao_Preferencial",
    },
    "fre_capital_social_desdobramento": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Capital_Social",
    },
    "fre_capital_social_desdobramento_classe_acao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "ID_Capital_Social", "Tipo_Classe_Acao_Preferencial",
    },
    "fre_capital_social_reducao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Capital_Social",
    },
    "fre_capital_social_reducao_classe_acao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "ID_Capital_Social", "Tipo_Classe_Acao_Preferencial",
    },
    "fre_direito_acao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Tipo_Classe_Acao", "Direito_Voto",
    },
    "fre_plano_recompra": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Plano_Recompra",
    },
    "fre_plano_recompra_classe_acao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "ID_Plano_Recompra", "Tipo_Classe_Acao_Preferencial",
    },
    "fre_valor_mobiliario_tesouraria_movimentacao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Classe_Valor_Mobiliario", "Data_Movimentacao",
    },
    "fre_valor_mobiliario_tesouraria_ultimo_exercicio": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Classe_Valor_Mobiliario", "Historico_Exercicio",
    },
    "fre_administrador_membro_conselho_fiscal": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Nome", "CPF", "Orgao_Administracao", "Data_Eleicao", "Data_Posse",
        "Cargo_Eletivo_Ocupado",
    },
    "fre_membro_comite": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Nome", "CPF", "Tipo_Comite",
    },
    "fre_relacao_subordinacao": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Nome_Administrador", "Nome_Pessoa_Relacionada", "Tipo_Relacao",
        "Cargo_Administrador", "Cargo_Pessoa_Relacionada",
        "Data_Inicio_Exercicio_Social", "Data_Fim_Exercicio_Social",
    },
    "fre_transacao_parte_relacionada": {
        "CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento",
        "Parte_Relacionada", "Documento_Parte_Relacionada", "Relacao_Emissor",
        "Data_Transacao", "Montante_Envolvido", "Saldo_Existente",
        "Montante_Interesse_Parte_Relacionada", "Posicao_Contratual_Emissor",
    },
}


def test_validate_member_header_accepts_valid_new_fre_row_kinds() -> None:
    for row_kind, required in _NEW_FRE_REQUIRED_HEADERS.items():
        result = validate_member_header(row_kind, list(required))
        assert result.status == "valid", f"{row_kind}: expected valid, got {result.status}"


def test_validate_member_header_rejects_missing_id_capital_social_for_capital_social_aumento() -> None:
    result = validate_member_header(
        "fre_capital_social_aumento",
        ["CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"],
    )

    assert result.status == "invalid"
    assert result.reason_code == "schema_inesperado"
    assert result.repairable is True
    assert "ID_Capital_Social" in result.details["missing_required_columns"]


def test_validate_member_header_rejects_missing_all_required_for_transacao_parte_relacionada() -> None:
    result = validate_member_header(
        "fre_transacao_parte_relacionada",
        ["CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"],
    )

    assert result.status == "invalid"
    assert result.reason_code == "schema_inesperado"
    missing = result.details["missing_required_columns"]
    assert "Parte_Relacionada" in missing
    assert "Documento_Parte_Relacionada" in missing
    assert "Relacao_Emissor" in missing
    assert "Data_Transacao" in missing
    assert "Montante_Envolvido" in missing
    assert "Saldo_Existente" in missing
    assert "Montante_Interesse_Parte_Relacionada" in missing
    assert "Posicao_Contratual_Emissor" in missing


def test_normalizacao_invalida_result_is_repairable_with_specific_error() -> None:
    result = invalid_result(
        "normalizacao_invalida: campo_obrigatorio_ausente",
        details={"erro": "campo_obrigatorio_ausente"},
        repairable=True,
    )

    assert result.status == "invalid"
    assert result.repairable is True
    assert result.reason_code is not None
    assert "campo_obrigatorio_ausente" in result.reason_code
    assert "normalizacao_invalida" in result.reason_code


def test_normalizar_reason_code_extracts_base_codigo_preserving_backward_compat() -> None:
    assert _normalizar_reason_code("normalizacao_invalida: campo_obrigatorio_ausente") == "normalizacao_invalida"
    assert _normalizar_reason_code("normalizacao_invalida: campo_obrigatorio_ausente") == "normalizacao_invalida"
    assert _normalizar_reason_code("companhia_nao_encontrada") == "companhia_nao_encontrada"
    assert _normalizar_reason_code("chave_natural_duplicada_conflitante") == "chave_natural_duplicada_conflitante"
    assert _normalizar_reason_code("schema_inesperado") == "schema_inesperado"
    assert _normalizar_reason_code(None) == "desconhecido"
    assert _normalizar_reason_code("") == "desconhecido"
    assert _normalizar_reason_code("normalizacao_invalida") == "normalizacao_invalida"


def test_create_quarantine_item_uses_normalizacao_invalida_motivo_codigo() -> None:
    session = _session()
    try:
        member, row = _staged_row(session)
        result = invalid_result(
            "normalizacao_invalida: campo_obrigatorio_ausente",
            details={"erro": "campo_obrigatorio_ausente"},
            repairable=True,
        )
        write_validation_result(session, ingestion_row=row, result=result)
        session.commit()
        session.refresh(row)

        assert row.validation_status == "invalid"
        assert row.validation_reason_code == "normalizacao_invalida: campo_obrigatorio_ausente"
        assert row.validation_details["details"]["erro"] == "campo_obrigatorio_ausente"
        assert row.validation_details["repairable"] is True
    finally:
        session.close()

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, cast

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFileMember, IngestionRow
from app.services.ingestion.normalizers import gerar_hash_canonico, normalizar_chave_natural
from app.services.ingestion.staging import register_row_event, update_row_validation


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reason_code: str | None
    severity: str
    details: dict[str, Any] = field(default_factory=dict)
    repairable: bool = False

    def to_json_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        return cast(dict[str, Any], json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)))


_REQUIRED_COLUMNS_BY_ROW_KIND: dict[str, set[str]] = {
    "cadastro_aberta": {"CNPJ_CIA", "CD_CVM", "DENOM_SOCIAL"},
    "cadastro_estrangeira": {"CNPJ", "CD_CVM", "DENOM_SOCIAL"},
    "dfp_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "itr_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "dfp_demonstracao": {"CNPJ_CIA", "DT_REFER", "VERSAO", "CD_CONTA"},
    "itr_demonstracao": {"CNPJ_CIA", "DT_REFER", "VERSAO", "CD_CONTA"},
    "dfp_composicao_capital": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "itr_composicao_capital": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "dfp_parecer": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "itr_parecer": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "fre_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "fca_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "fre_auditor": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Auditor"},
    "fre_capital_social": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Capital_Social"},
    "fre_posicao_acionaria": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Acionista"},
    "fre_remuneracao_total_orgao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Orgao_Administracao",
    },
    "fre_empregado_posicao_genero": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"},
    "fre_participacao_sociedade": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Sociedade",
    },
    "fre_empregado_posicao_local": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Posicao"},
    "fre_empregado_posicao_faixa_etaria": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Posicao"},
    "fre_empregado_posicao_declaracao_raca": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Posicao",
    },
    "fre_empregado_pcd": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Posicao",
    },
    "fre_empregado_local_faixa_etaria": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Local"},
    "fre_empregado_local_declaracao_raca": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Local"},
    "fre_empregado_local_declaracao_genero": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Local"},
    "fre_administrador_pcd": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Orgao_Administracao"},
    "fre_administrador_declaracao_genero": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Orgao_Administracao"},
    "fre_administrador_declaracao_raca": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Orgao_Administracao"},
    "fre_responsavel": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"},
    "fre_relacao_familiar": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome_Administrador",
        "Nome_Pessoa_Relacionada",
    },
    "fre_capital_social_classe_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
    },
    "fre_capital_social_titulo_conversivel": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
    },
    "fre_distribuicao_capital": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"},
    "fre_distribuicao_capital_classe_acao": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"},
    "fre_posicao_acionaria_classe_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Acionista",
    },
    "fre_remuneracao_maxima_minima_media": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Orgao_Administracao",
    },
    "fre_remuneracao_variavel": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Orgao_Administracao"},
    "fre_remuneracao_acao": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Orgao_Administracao"},
    "fre_acao_entregue": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Orgao_Administracao"},
    "fre_volume_valor_mobiliario": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Classe_Valor_Mobiliario",
    },
    "fre_outro_valor_mobiliario": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome_Valor_Mobiliario",
    },
    "fre_titular_valor_mobiliario": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome_Titular",
        "Classe_Valor_Mobiliario",
    },
    "fre_mercado_estrangeiro": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome_Mercado",
    },
    "fre_titulo_exterior": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome_Titulo",
    },
    "fre_capital_social_aumento": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
    },
    "fre_capital_social_aumento_classe_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
        "Tipo_Classe_Acao_Preferencial",
    },
    "fre_capital_social_desdobramento": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
    },
    "fre_capital_social_desdobramento_classe_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
        "Tipo_Classe_Acao_Preferencial",
    },
    "fre_capital_social_reducao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
    },
    "fre_capital_social_reducao_classe_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Capital_Social",
        "Tipo_Classe_Acao_Preferencial",
    },
    "fre_direito_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Tipo_Classe_Acao",
        "Direito_Voto",
    },
    "fre_plano_recompra": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Plano_Recompra",
    },
    "fre_plano_recompra_classe_acao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "ID_Plano_Recompra",
        "Especie_Acao",
    },
    "fre_valor_mobiliario_tesouraria_movimentacao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Classe_Valor_Mobiliario",
        "Data_Movimentacao",
    },
    "fre_valor_mobiliario_tesouraria_ultimo_exercicio": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Classe_Valor_Mobiliario",
        "Historico_Exercicio",
    },
    "fre_administrador_membro_conselho_fiscal": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome",
        "CPF",
        "Orgao_Administracao",
        "Data_Eleicao",
        "Data_Posse",
        "Cargo_Eletivo_Ocupado",
    },
    "fre_membro_comite": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome",
        "CPF",
        "Tipo_Comite",
    },
    "fre_relacao_subordinacao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Nome_Administrador",
        "Nome_Pessoa_Relacionada",
        "Tipo_Relacao",
        "Cargo_Administrador",
        "Cargo_Pessoa_Relacionada",
        "Data_Inicio_Exercicio_Social",
        "Data_Fim_Exercicio_Social",
    },
    "fre_transacao_parte_relacionada": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Parte_Relacionada",
        "Documento_Parte_Relacionada",
        "Relacao_Emissor",
        "Data_Transacao",
        "Montante_Envolvido",
        "Saldo_Existente",
        "Montante_Interesse_Parte_Relacionada",
        "Posicao_Contratual_Emissor",
    },
    "fca_geral": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Codigo_CVM"},
    "fca_endereco": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Tipo_Endereco"},
    "fca_dri": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Responsavel"},
    "fca_auditor": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Auditor"},
    "fca_valor_mobiliario": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Valor_Mobiliario"},
    "fca_escriturador": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Escriturador"},
    "fca_canal_divulgacao": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Canal_Divulgacao"},
    "fca_departamento_acionistas": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"},
    "fca_pais_estrangeiro_negociacao": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "Pais"},
    "ipe_documento": {
        "CNPJ_Companhia",
        "Nome_Companhia",
        "Data_Referencia",
        "Categoria",
        "Tipo",
        "Especie",
        "Assunto",
        "Data_Entrega",
        "Tipo_Apresentacao",
        "Versao",
        "Link_Download",
    },
    "vlmo_documento": {
        "CNPJ_Companhia",
        "Nome_Companhia",
        "Codigo_CVM",
        "Data_Referencia",
        "Categoria",
        "Tipo",
        "Data_Entrega",
        "Tipo_Apresentacao",
        "Versao",
        "Link_Download",
    },
    "vlmo_consolidado": {
        "CNPJ_Companhia",
        "Nome_Companhia",
        "Data_Referencia",
        "Versao",
        "Tipo_Empresa",
        "Empresa",
        "Tipo_Cargo",
        "Tipo_Movimentacao",
        "Descricao_Movimentacao",
        "Tipo_Operacao",
        "Tipo_Ativo",
        "Caracteristica_Valor_Mobiliario",
        "Intermediario",
        "Data_Movimentacao",
        "Quantidade",
        "Preco_Unitario",
        "Volume",
    },
}


def ok_result(*, details: dict[str, Any] | None = None) -> ValidationResult:
    return ValidationResult(status="valid", reason_code=None, severity="info", details=details or {}, repairable=False)


def invalid_result(
    reason_code: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
    repairable: bool = False,
) -> ValidationResult:
    return ValidationResult(
        status="invalid",
        reason_code=reason_code,
        severity=severity,
        details=details or {},
        repairable=repairable,
    )


def validate_member_header(row_kind: str, header: list[str] | None) -> ValidationResult:
    header_list = header or []
    header_set = set(header_list)
    required = _REQUIRED_COLUMNS_BY_ROW_KIND.get(row_kind, set())
    if not required:
        return ok_result(details={"row_kind": row_kind, "unknown_columns": sorted(header_set)})

    missing = sorted(required - header_set)
    unknown = sorted(header_set - required)
    if missing:
        return invalid_result(
            "schema_inesperado",
            details={
                "row_kind": row_kind,
                "missing_required_columns": missing,
                "unknown_columns": unknown,
            },
            repairable=True,
        )
    return ok_result(details={"row_kind": row_kind, "unknown_columns": unknown})


NaturalKeyBuilder = dict[str, Any]


def _natural_key_documento(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
    }


def _natural_key_demonstracao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "tipo_demonstracao": dados.get("tipo_demonstracao"),
        "escopo_demonstracao": dados.get("escopo_demonstracao"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
        "grupo_demonstracao": dados.get("grupo_demonstracao"),
        "ordem_exercicio": dados.get("ordem_exercicio"),
        "data_inicio_exercicio": dados.get("data_inicio_exercicio"),
        "data_fim_exercicio": dados.get("data_fim_exercicio"),
        "codigo_conta": dados.get("codigo_conta"),
        "coluna_df": dados.get("coluna_df") or "",
    }


def _natural_key_composicao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
    }


def _natural_key_parecer(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
        "tipo_relatorio_auditor": dados.get("tipo_relatorio_auditor"),
        "tipo_parecer_declaracao": dados.get("tipo_parecer_declaracao"),
        "numero_item_parecer_declaracao": dados.get("numero_item_parecer_declaracao"),
    }


def _natural_key_cadastro_registro(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "fonte_cadastro": dados.get("fonte_cadastro"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "codigo_cvm": dados.get("codigo_cvm"),
        "hash_sem_mercado": dados.get("hash_sem_mercado"),
    }


def _natural_key_fre_auditor(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_auditor": dados.get("id_auditor"),
    }


def _natural_key_fre_capital_social(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
    }


def _natural_key_fre_posicao_acionaria(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_acionista": dados.get("id_acionista"),
    }


def _natural_key_fre_remuneracao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
    }


def _natural_key_fre_empregado_posicao_genero(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "posicao": dados.get("posicao"),
    }


def _natural_key_fre_participacao_sociedade(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_sociedade": dados.get("id_sociedade"),
    }


def _natural_key_fre_empregado_posicao_local(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "posicao": dados.get("posicao"),
    }


def _natural_key_fre_empregado_posicao_faixa_etaria(dados: dict[str, Any]) -> dict[str, Any]:
    return _natural_key_fre_empregado_posicao_local(dados)


def _natural_key_fre_empregado_posicao_declaracao_raca(dados: dict[str, Any]) -> dict[str, Any]:
    return _natural_key_fre_empregado_posicao_local(dados)


def _natural_key_fre_empregado_pcd(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "codigo_posicao": dados.get("codigo_posicao"),
        "posicao": dados.get("posicao"),
    }


def _natural_key_fre_empregado_local_faixa_etaria(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "local": dados.get("local"),
    }


def _natural_key_fre_empregado_local_declaracao_raca(dados: dict[str, Any]) -> dict[str, Any]:
    return _natural_key_fre_empregado_local_faixa_etaria(dados)


def _natural_key_fre_empregado_local_declaracao_genero(dados: dict[str, Any]) -> dict[str, Any]:
    return _natural_key_fre_empregado_local_faixa_etaria(dados)


def _natural_key_fre_administrador_declaracao_genero(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
    }


def _natural_key_fre_administrador_pcd(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
    }


def _natural_key_fre_administrador_declaracao_raca(dados: dict[str, Any]) -> dict[str, Any]:
    return _natural_key_fre_administrador_pcd(dados)


def _natural_key_fre_responsavel(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome_responsavel": dados.get("nome_responsavel"),
        "cargo_responsavel": dados.get("cargo_responsavel"),
    }


def _natural_key_fre_capital_social_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
        "tipo_classe_acao_preferencial": dados.get("tipo_classe_acao_preferencial"),
    }


def _natural_key_fre_capital_social_titulo_conversivel(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
        "titulo_conversivel_acao": dados.get("titulo_conversivel_acao"),
    }


def _natural_key_fre_distribuicao_capital(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
    }


def _natural_key_fre_distribuicao_capital_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "sigla_classe_acoes_preferenciais": dados.get("sigla_classe_acoes_preferenciais"),
    }


def _natural_key_fre_posicao_acionaria_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_acionista": dados.get("id_acionista"),
        "tipo_classe_acao_preferencial": dados.get("tipo_classe_acao_preferencial"),
        "quantidade_acoes": dados.get("quantidade_acoes"),
        "percentual_acoes": dados.get("percentual_acoes"),
    }


def _natural_key_fre_remuneracao_maxima_minima_media(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
    }


def _natural_key_fre_remuneracao_variavel(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
    }


def _natural_key_fre_remuneracao_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
    }


def _natural_key_fre_acao_entregue(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
    }


def _natural_key_fca_geral(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
    }


def _natural_key_fca_endereco(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "tipo_endereco": dados.get("tipo_endereco"),
        "logradouro": dados.get("logradouro"),
        "cep": dados.get("cep"),
    }


def _natural_key_fca_dri(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "cpf_responsavel": dados.get("cpf_responsavel"),
        "tipo_responsavel": dados.get("tipo_responsavel"),
        "data_inicio_atuacao": dados.get("data_inicio_atuacao"),
        "tipo_endereco": dados.get("tipo_endereco"),
        "logradouro": dados.get("logradouro"),
        "cep": dados.get("cep"),
        "telefone": dados.get("telefone"),
        "email_dri": dados.get("email_dri"),
    }


def _natural_key_fca_auditor(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "cpf_cnpj_auditor": dados.get("cpf_cnpj_auditor"),
        "codigo_cvm_auditor": dados.get("codigo_cvm_auditor"),
        "data_inicio_atuacao_auditor": dados.get("data_inicio_atuacao_auditor"),
        "data_fim_atuacao_auditor": dados.get("data_fim_atuacao_auditor"),
        "responsavel_tecnico": dados.get("responsavel_tecnico"),
        "cpf_responsavel_tecnico": dados.get("cpf_responsavel_tecnico"),
        "data_inicio_atuacao_responsavel_tecnico": dados.get("data_inicio_atuacao_responsavel_tecnico"),
    }


def _natural_key_fca_valor_mobiliario(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "tipo_valor_mobiliario": dados.get("tipo_valor_mobiliario"),
        "codigo_negociacao": dados.get("codigo_negociacao"),
        "mercado": dados.get("mercado"),
        "sigla_classe_acao_preferencial": dados.get("sigla_classe_acao_preferencial"),
        "classe_acao_preferencial": dados.get("classe_acao_preferencial"),
        "composicao_bdr_unit": dados.get("composicao_bdr_unit"),
        "data_inicio_negociacao": dados.get("data_inicio_negociacao"),
        "data_fim_negociacao": dados.get("data_fim_negociacao"),
        "data_inicio_listagem": dados.get("data_inicio_listagem"),
        "data_fim_listagem": dados.get("data_fim_listagem"),
    }


def _natural_key_fca_canal_divulgacao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "canal_divulgacao": dados.get("canal_divulgacao"),
        "sigla_uf": dados.get("sigla_uf"),
    }


def _natural_key_fca_departamento_acionistas(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "contato": dados.get("contato"),
        "email": dados.get("email"),
        "tipo_endereco": dados.get("tipo_endereco"),
    }


def _natural_key_fca_escriturador(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "escriturador": dados.get("escriturador"),
        "cnpj_escriturador": dados.get("cnpj_escriturador"),
    }


def _natural_key_fca_pais_estrangeiro_negociacao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "pais": dados.get("pais"),
        "data_admissao_negociacao": dados.get("data_admissao_negociacao"),
    }


def _natural_key_ipe_documento(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "codigo_cvm": dados.get("codigo_cvm"),
        "data_referencia": dados.get("data_referencia"),
        "categoria": dados.get("categoria"),
        "tipo": dados.get("tipo"),
        "especie": dados.get("especie"),
        "assunto": dados.get("assunto"),
        "data_entrega": dados.get("data_entrega"),
        "protocolo_entrega": dados.get("protocolo_entrega"),
        "versao": dados.get("versao"),
    }


def _natural_key_vlmo_documento(dados: dict[str, Any]) -> dict[str, Any]:
    protocolo_entrega = dados.get("protocolo_entrega")
    if protocolo_entrega is not None:
        return {"protocolo_entrega": protocolo_entrega, "versao": dados.get("versao")}
    return {
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "codigo_cvm": dados.get("codigo_cvm"),
        "data_referencia": dados.get("data_referencia"),
        "categoria": dados.get("categoria"),
        "tipo": dados.get("tipo"),
        "data_entrega": dados.get("data_entrega"),
        "versao": dados.get("versao"),
    }


def _natural_key_vlmo_consolidado(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
        "linha_origem": dados.get("linha_origem"),
    }


def _natural_key_cgvn_documento(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
    }


def _natural_key_cgvn_pratica(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
        "id_item": dados.get("id_item"),
        "linha_origem": dados.get("linha_origem"),
    }


def _natural_key_fre_administrador_membro_conselho_fiscal(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome": dados.get("nome"),
        "cpf": dados.get("cpf"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_eleicao": dados.get("data_eleicao"),
        "data_posse": dados.get("data_posse"),
        "cargo_eletivo_ocupado": dados.get("cargo_eletivo_ocupado"),
        "outro_cargo_funcao": dados.get("outro_cargo_funcao"),
    }


def _natural_key_fre_membro_comite(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome": dados.get("nome"),
        "cpf": dados.get("cpf"),
        "tipo_comite": dados.get("tipo_comite"),
        "descricao_outros_comites": dados.get("descricao_outros_comites"),
    }


def _natural_key_fre_relacao_familiar(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome_administrador": dados.get("nome_administrador"),
        "nome_pessoa_relacionada": dados.get("nome_pessoa_relacionada"),
        "tipo_parentesco": dados.get("tipo_parentesco"),
        "cnpj_emissor_pessoa_relacionada": dados.get("cnpj_emissor_pessoa_relacionada"),
        "nome_emissor_pessoa_relacionada": dados.get("nome_emissor_pessoa_relacionada"),
        "cargo_Pessoa_relacionada": dados.get("cargo_Pessoa_relacionada"),
        "cnpj_emissor": dados.get("cnpj_emissor"),
        "nome_emissor": dados.get("nome_emissor"),
        "cargo_administrador": dados.get("cargo_administrador"),
    }


def _natural_key_fre_relacao_subordinacao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
        "nome_administrador": dados.get("nome_administrador"),
        "nome_pessoa_relacionada": dados.get("nome_pessoa_relacionada"),
        "tipo_relacao": dados.get("tipo_relacao"),
        "cargo_administrador": dados.get("cargo_administrador"),
        "cargo_pessoa_relacionada": dados.get("cargo_pessoa_relacionada"),
    }


def _natural_key_fre_transacao_parte_relacionada(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "parte_relacionada": dados.get("parte_relacionada"),
        "documento_parte_relacionada": dados.get("documento_parte_relacionada"),
        "relacao_emissor": dados.get("relacao_emissor"),
        "data_transacao": dados.get("data_transacao"),
        "montante_envolvido": dados.get("montante_envolvido"),
        "saldo_existente": dados.get("saldo_existente"),
        "montante_interesse_parte_relacionada": dados.get("montante_interesse_parte_relacionada"),
        "posicao_contratual_emissor": dados.get("posicao_contratual_emissor"),
    }


def _natural_key_fre_capital_social_aumento(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
    }


def _natural_key_fre_capital_social_aumento_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
        "tipo_classe_acao_preferencial": dados.get("tipo_classe_acao_preferencial"),
    }


def _natural_key_fre_capital_social_desdobramento(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
    }


def _natural_key_fre_capital_social_desdobramento_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
        "tipo_classe_acao_preferencial": dados.get("tipo_classe_acao_preferencial"),
    }


def _natural_key_fre_capital_social_reducao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
    }


def _natural_key_fre_capital_social_reducao_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
        "tipo_classe_acao_preferencial": dados.get("tipo_classe_acao_preferencial"),
    }


def _natural_key_fre_direito_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "tipo_classe_acao": dados.get("tipo_classe_acao"),
        "direito_voto": dados.get("direito_voto"),
    }


def _natural_key_fre_volume_valor_mobiliario(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "classe_valor_mobiliario": dados.get("classe_valor_mobiliario"),
    }


def _natural_key_fre_outro_valor_mobiliario(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome_valor_mobiliario": dados.get("nome_valor_mobiliario"),
    }


def _natural_key_fre_titular_valor_mobiliario(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome_titular": dados.get("nome_titular"),
        "classe_valor_mobiliario": dados.get("classe_valor_mobiliario"),
    }


def _natural_key_fre_mercado_estrangeiro(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome_mercado": dados.get("nome_mercado"),
    }


def _natural_key_fre_titulo_exterior(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "nome_titulo": dados.get("nome_titulo"),
    }


def _natural_key_fre_plano_recompra(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_plano_recompra": dados.get("id_plano_recompra"),
    }


def _natural_key_fre_plano_recompra_classe_acao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_plano_recompra": dados.get("id_plano_recompra"),
        "especie_acao": dados.get("especie_acao"),
        "tipo_classe_acao_preferencial": dados.get("tipo_classe_acao_preferencial"),
    }


def _natural_key_fre_valor_mobiliario_tesouraria_movimentacao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "classe_valor_mobiliario": dados.get("classe_valor_mobiliario"),
        "data_movimentacao": dados.get("data_movimentacao"),
    }


def _natural_key_fre_valor_mobiliario_tesouraria_ultimo_exercicio(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "classe_valor_mobiliario": dados.get("classe_valor_mobiliario"),
        "historico_exercicio": dados.get("historico_exercicio"),
    }


_NATURAL_KEY_BUILDERS: dict[str, Any] = {
    "fre_capital_social_aumento": _natural_key_fre_capital_social_aumento,
    "fre_capital_social_aumento_classe_acao": _natural_key_fre_capital_social_aumento_classe_acao,
    "fre_capital_social_desdobramento": _natural_key_fre_capital_social_desdobramento,
    "fre_capital_social_desdobramento_classe_acao": _natural_key_fre_capital_social_desdobramento_classe_acao,
    "fre_capital_social_reducao": _natural_key_fre_capital_social_reducao,
    "fre_capital_social_reducao_classe_acao": _natural_key_fre_capital_social_reducao_classe_acao,
    "fre_direito_acao": _natural_key_fre_direito_acao,
    "fre_volume_valor_mobiliario": _natural_key_fre_volume_valor_mobiliario,
    "fre_outro_valor_mobiliario": _natural_key_fre_outro_valor_mobiliario,
    "fre_titular_valor_mobiliario": _natural_key_fre_titular_valor_mobiliario,
    "fre_mercado_estrangeiro": _natural_key_fre_mercado_estrangeiro,
    "fre_titulo_exterior": _natural_key_fre_titulo_exterior,
    "fre_plano_recompra": _natural_key_fre_plano_recompra,
    "fre_plano_recompra_classe_acao": _natural_key_fre_plano_recompra_classe_acao,
    "fre_valor_mobiliario_tesouraria_movimentacao": _natural_key_fre_valor_mobiliario_tesouraria_movimentacao,
    "fre_valor_mobiliario_tesouraria_ultimo_exercicio": _natural_key_fre_valor_mobiliario_tesouraria_ultimo_exercicio,
    "fre_administrador_membro_conselho_fiscal": _natural_key_fre_administrador_membro_conselho_fiscal,
    "fre_membro_comite": _natural_key_fre_membro_comite,
    "fre_relacao_familiar": _natural_key_fre_relacao_familiar,
    "fre_relacao_subordinacao": _natural_key_fre_relacao_subordinacao,
    "fre_transacao_parte_relacionada": _natural_key_fre_transacao_parte_relacionada,
    "cadastro_registro_cvm": _natural_key_cadastro_registro,
    "dfp_documento": _natural_key_documento,
    "itr_documento": _natural_key_documento,
    "dfp_demonstracao": _natural_key_demonstracao,
    "itr_demonstracao": _natural_key_demonstracao,
    "dfp_composicao_capital": _natural_key_composicao,
    "itr_composicao_capital": _natural_key_composicao,
    "dfp_parecer": _natural_key_parecer,
    "itr_parecer": _natural_key_parecer,
    "fre_documento": _natural_key_documento,
    "fca_documento": _natural_key_documento,
    "fre_auditor": _natural_key_fre_auditor,
    "fre_capital_social": _natural_key_fre_capital_social,
    "fre_posicao_acionaria": _natural_key_fre_posicao_acionaria,
    "fre_remuneracao_total_orgao": _natural_key_fre_remuneracao,
    "fre_empregado_posicao_genero": _natural_key_fre_empregado_posicao_genero,
    "fre_participacao_sociedade": _natural_key_fre_participacao_sociedade,
    "fre_empregado_posicao_local": _natural_key_fre_empregado_posicao_local,
    "fre_empregado_posicao_faixa_etaria": _natural_key_fre_empregado_posicao_faixa_etaria,
    "fre_empregado_posicao_declaracao_raca": _natural_key_fre_empregado_posicao_declaracao_raca,
    "fre_empregado_pcd": _natural_key_fre_empregado_pcd,
    "fre_empregado_local_faixa_etaria": _natural_key_fre_empregado_local_faixa_etaria,
    "fre_empregado_local_declaracao_raca": _natural_key_fre_empregado_local_declaracao_raca,
    "fre_empregado_local_declaracao_genero": _natural_key_fre_empregado_local_declaracao_genero,
    "fre_administrador_pcd": _natural_key_fre_administrador_pcd,
    "fre_administrador_declaracao_genero": _natural_key_fre_administrador_declaracao_genero,
    "fre_administrador_declaracao_raca": _natural_key_fre_administrador_declaracao_raca,
    "fre_responsavel": _natural_key_fre_responsavel,
    "fre_capital_social_classe_acao": _natural_key_fre_capital_social_classe_acao,
    "fre_capital_social_titulo_conversivel": _natural_key_fre_capital_social_titulo_conversivel,
    "fre_distribuicao_capital": _natural_key_fre_distribuicao_capital,
    "fre_distribuicao_capital_classe_acao": _natural_key_fre_distribuicao_capital_classe_acao,
    "fre_posicao_acionaria_classe_acao": _natural_key_fre_posicao_acionaria_classe_acao,
    "fre_remuneracao_maxima_minima_media": _natural_key_fre_remuneracao_maxima_minima_media,
    "fre_remuneracao_variavel": _natural_key_fre_remuneracao_variavel,
    "fre_remuneracao_acao": _natural_key_fre_remuneracao_acao,
    "fre_acao_entregue": _natural_key_fre_acao_entregue,
    "fca_geral": _natural_key_fca_geral,
    "fca_endereco": _natural_key_fca_endereco,
    "fca_dri": _natural_key_fca_dri,
    "fca_auditor": _natural_key_fca_auditor,
    "fca_valor_mobiliario": _natural_key_fca_valor_mobiliario,
    "fca_escriturador": _natural_key_fca_escriturador,
    "fca_canal_divulgacao": _natural_key_fca_canal_divulgacao,
    "fca_departamento_acionistas": _natural_key_fca_departamento_acionistas,
    "fca_pais_estrangeiro_negociacao": _natural_key_fca_pais_estrangeiro_negociacao,
    "ipe_documento": _natural_key_ipe_documento,
    "vlmo_documento": _natural_key_vlmo_documento,
    "vlmo_consolidado": _natural_key_vlmo_consolidado,
    "cgvn_documento": _natural_key_cgvn_documento,
    "cgvn_pratica": _natural_key_cgvn_pratica,
}


def build_natural_key(row_kind: str, normalized_data: dict[str, Any]) -> dict[str, Any]:
    builder = _NATURAL_KEY_BUILDERS.get(row_kind)
    if builder is None:
        raise KeyError(f"natural_key_builder_nao_encontrado: {row_kind}")
    return normalizar_chave_natural(builder(normalized_data))


def _normalized_diff(previous_data: dict[str, Any], current_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(previous_data) | set(current_data)):
        before = previous_data.get(key)
        after = current_data.get(key)
        if before != after:
            diff[key] = {"before": before, "after": after}
    return diff


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _financeiro_zero_shadow_duplicate_resolution(
    *,
    row_kind: str,
    seen_data: dict[str, Any],
    comparison_data: dict[str, Any],
) -> ValidationResult | None:
    if row_kind not in {"dfp_demonstracao", "itr_demonstracao"}:
        return None
    diff = _normalized_diff(seen_data, comparison_data)
    if set(diff.keys()) != {"valor_conta"}:
        return None
    before = _as_decimal(diff["valor_conta"]["before"])
    after = _as_decimal(diff["valor_conta"]["after"])
    if before is None or after is None:
        return None
    if before == after:
        return ValidationResult(
            status="ignored_duplicate",
            reason_code="ignored_duplicate",
            severity="info",
            details={"duplicate_status": "equal_numeric"},
            repairable=False,
        )
    if before == Decimal("0") and after != Decimal("0"):
        seen_data["valor_conta"] = comparison_data["valor_conta"]
        return ValidationResult(
            status="ignored_duplicate",
            reason_code="ignored_duplicate",
            severity="info",
            details={"duplicate_status": "preferred_non_zero"},
            repairable=False,
        )
    if after == Decimal("0") and before != Decimal("0"):
        return ValidationResult(
            status="ignored_duplicate",
            reason_code="ignored_duplicate",
            severity="info",
            details={"duplicate_status": "ignored_zero_shadow"},
            repairable=False,
        )
    return None


_DUPLICATE_COMPARISON_EXCLUDED_FIELDS = {
    "arquivo_origem",
    "ano_origem",
    "linha_origem",
    "hash_origem",
    "companhia_id",
}


def build_duplicate_comparison_data(normalized_data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in normalizar_chave_natural(normalized_data).items()
        if key not in _DUPLICATE_COMPARISON_EXCLUDED_FIELDS
    }


def classify_duplicate(
    *,
    row_kind: str,
    natural_key: dict[str, Any],
    normalized_hash: str,
    normalized_data: dict[str, Any],
    seen_by_key: dict[str, dict[str, Any]],
) -> ValidationResult:
    natural_key_payload = normalizar_chave_natural(natural_key)
    natural_key_json = json.dumps(natural_key_payload, ensure_ascii=False, sort_keys=True, default=str)
    comparison_data = build_duplicate_comparison_data(normalized_data)
    comparison_hash = gerar_hash_canonico(comparison_data)
    seen = seen_by_key.get(natural_key_json)
    if seen is None:
        seen_by_key[natural_key_json] = {
            "normalized_hash": comparison_hash,
            "normalized_data": comparison_data,
        }
        return ok_result(details={"duplicate_status": "new"})

    if seen["normalized_hash"] == comparison_hash:
        return ValidationResult(
            status="ignored_duplicate",
            reason_code="ignored_duplicate",
            severity="info",
            details={"natural_key": natural_key_payload},
            repairable=False,
        )

    source_specific = _financeiro_zero_shadow_duplicate_resolution(
        row_kind=row_kind,
        seen_data=seen["normalized_data"],
        comparison_data=comparison_data,
    )
    if source_specific is not None:
        seen["normalized_hash"] = gerar_hash_canonico(seen["normalized_data"])
        return source_specific

    seen["normalized_hash"] = comparison_hash
    seen["normalized_data"] = comparison_data
    return ok_result(details={"duplicate_status": "updated"})


def write_validation_result(
    db: Session,
    *,
    ingestion_row: IngestionRow,
    result: ValidationResult,
    normalized_data: dict[str, Any] | None = None,
    natural_key: dict[str, Any] | None = None,
    created_by: str = "validation",
) -> IngestionRow:
    if result.status in {"valid", "ignored_duplicate"}:
        return ingestion_row
    normalized_hash = None
    normalized_data_payload = None
    natural_key_payload = None
    if normalized_data is not None:
        normalized_hash = gerar_hash_canonico(normalized_data)
        normalized_data_payload = normalizar_chave_natural(normalized_data)
    if natural_key is not None:
        natural_key_payload = normalizar_chave_natural(natural_key)
    update_row_validation(
        ingestion_row,
        validation_status=result.status,
        validation_reason_code=result.reason_code,
        validation_details=result.to_json_payload(),
        normalized_data=normalized_data_payload,
        normalized_hash=normalized_hash,
        natural_key=natural_key_payload,
    )
    register_row_event(
        db,
        ingestion_row=ingestion_row,
        event_type="validated" if result.status in {"valid", "ignored_duplicate"} else "quarantined",
        event_payload=result.to_json_payload(),
        created_by=created_by,
    )
    return ingestion_row


def update_member_schema_validation(
    member: IngestionFileMember,
    *,
    result: ValidationResult,
) -> IngestionFileMember:
    member.schema_status = result.status
    member.schema_message = json.dumps(result.to_json_payload(), ensure_ascii=False, sort_keys=True, default=str)
    return member

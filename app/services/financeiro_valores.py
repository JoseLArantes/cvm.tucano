from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import case

from app.models.financeiro import DemonstracaoFinanceira
from app.services.normalizacao import normalizar_texto

_ESCALA_FATORES: dict[str, Decimal] = {
    "UNIDADE": Decimal("1"),
    "MIL": Decimal("1000"),
    "MILHAO": Decimal("1000000"),
    "MILHÃO": Decimal("1000000"),
}


def normalizar_decimal_financeiro(valor: Any) -> Decimal | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    if texto.upper() in {"-", "N/A", "ND", "N/D", "NI", "NA", "N.A.", "N.A"}:
        return None
    texto = texto.strip()
    if "," in texto:
        raise ValueError(f"Separador decimal invalido para dado estruturado CVM: {valor}")
    if texto.count(".") > 1:
        raise ValueError(f"Separador de milhares invalido para dado estruturado CVM: {valor}")
    return Decimal(texto)


def validar_escala_moeda(escala_moeda: str | None) -> str:
    escala = normalizar_texto(escala_moeda)
    if escala is None:
        raise ValueError("escala_moeda_ausente")
    escala_upper = escala.upper()
    if escala_upper not in _ESCALA_FATORES:
        raise ValueError(f"escala_moeda_desconhecida: {escala}")
    return escala_upper


def fator_escala_moeda(escala_moeda: str | None) -> Decimal:
    return _ESCALA_FATORES[validar_escala_moeda(escala_moeda)]


def valor_conta_ajustado(valor_conta_reportado: Decimal | None, escala_moeda: str | None) -> Decimal | None:
    if valor_conta_reportado is None:
        return None
    return valor_conta_reportado * fator_escala_moeda(escala_moeda)


def expressao_sql_valor_conta_ajustado() -> Any:
    return DemonstracaoFinanceira.valor_conta * case(
        (DemonstracaoFinanceira.escala_moeda == "MIL", 1000),
        (DemonstracaoFinanceira.escala_moeda == "MILHAO", 1000000),
        (DemonstracaoFinanceira.escala_moeda == "MILHÃO", 1000000),
        (DemonstracaoFinanceira.escala_moeda == "UNIDADE", 1),
        else_=None,
    )


def serializar_demonstracao_financeira(item: DemonstracaoFinanceira) -> dict[str, Any]:
    valor_reportado = item.valor_conta
    fator_escala = fator_escala_moeda(item.escala_moeda)
    valor_ajustado = valor_conta_ajustado(valor_reportado, item.escala_moeda)
    return {
        "id": item.id,
        "companhia_id": item.companhia_id,
        "tipo_formulario": item.tipo_formulario,
        "tipo_demonstracao": item.tipo_demonstracao,
        "escopo_demonstracao": item.escopo_demonstracao,
        "cnpj_companhia": item.cnpj_companhia,
        "codigo_cvm": item.codigo_cvm,
        "data_referencia": item.data_referencia,
        "versao": item.versao,
        "denominacao_companhia": item.denominacao_companhia,
        "grupo_demonstracao": item.grupo_demonstracao,
        "moeda": item.moeda,
        "escala_moeda": item.escala_moeda,
        "fator_escala_moeda": int(fator_escala),
        "ordem_exercicio": item.ordem_exercicio,
        "data_inicio_exercicio": item.data_inicio_exercicio,
        "data_fim_exercicio": item.data_fim_exercicio,
        "codigo_conta": item.codigo_conta,
        "coluna_df": item.coluna_df,
        "descricao_conta": item.descricao_conta,
        "valor_conta": valor_ajustado,
        "valor_conta_reportado": valor_reportado,
        "conta_fixa": item.conta_fixa,
        "arquivo_origem": item.arquivo_origem,
        "ano_origem": item.ano_origem,
        "linha_origem": item.linha_origem,
        "criado_em": item.criado_em,
        "sincronizado_em": item.sincronizado_em,
        "alterado_em": item.alterado_em,
    }


def serializar_exportacao_linha(row: Any, columns: list[str]) -> dict[str, Any]:
    row_dict = {col: getattr(row, col) for col in columns if hasattr(row, col)}
    if isinstance(row, DemonstracaoFinanceira):
        serialized = serializar_demonstracao_financeira(row)
        row_dict.update(
            valor_conta=serialized["valor_conta"],
            valor_conta_reportado=serialized["valor_conta_reportado"],
            fator_escala_moeda=serialized["fator_escala_moeda"],
        )
    return row_dict


def colunas_exportacao(model: type[Any], columns: list[str]) -> list[str]:
    if model is DemonstracaoFinanceira:
        extended = []
        inserted = False
        for col in columns:
            extended.append(col)
            if col == "valor_conta":
                extended.append("valor_conta_reportado")
                inserted = True
            if col == "escala_moeda":
                extended.append("fator_escala_moeda")
        if not inserted:
            extended.extend(["valor_conta_reportado", "fator_escala_moeda"])
        return extended
    return columns

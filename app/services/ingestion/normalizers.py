from __future__ import annotations

import json
import unicodedata
from typing import Any, cast

from app.services.normalizacao import (
    gerar_hash_canonico,
    normalizar_cnpj,
    normalizar_data,
    normalizar_decimal_cvm,
    normalizar_inteiro,
    normalizar_texto,
)


def normalizar_cnpj_opcional(valor: Any) -> str | None:
    texto = "".join(char for char in str(valor or "") if char.isdigit())
    if not texto:
        return None
    return normalizar_cnpj(texto)


def normalizar_codigo_cvm(valor: Any) -> int | None:
    return normalizar_inteiro(valor)


def normalizar_nome_emissor_chave(valor: Any) -> str | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    return unicodedata.normalize("NFKC", texto).upper()


def normalizar_tipo_mercado(valor: Any) -> str | None:
    return normalizar_texto(valor)


def normalizar_header(header: list[str] | None) -> list[str]:
    if not header:
        return []
    return [unicodedata.normalize("NFKC", coluna).strip().lstrip("\ufeff") for coluna in header]


def normalizar_chave_natural(valor: dict[str, Any]) -> dict[str, Any]:
    texto = json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)
    return cast(dict[str, Any], json.loads(texto))


__all__ = [
    "gerar_hash_canonico",
    "normalizar_chave_natural",
    "normalizar_cnpj",
    "normalizar_cnpj_opcional",
    "normalizar_codigo_cvm",
    "normalizar_data",
    "normalizar_decimal_cvm",
    "normalizar_header",
    "normalizar_inteiro",
    "normalizar_nome_emissor_chave",
    "normalizar_texto",
    "normalizar_tipo_mercado",
]

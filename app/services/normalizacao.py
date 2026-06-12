import hashlib
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any


def normalizar_texto(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if texto.upper() in {"NULL", "NAN", "NONE"}:
        return None
    return " ".join(texto.split())


def normalizar_cnpj(valor: str | None) -> str:
    if valor is None:
        raise ValueError("CNPJ ausente.")
    numeros = re.sub(r"\D", "", valor)
    if len(numeros) != 14:
        raise ValueError(f"CNPJ invalido: {valor}")
    return numeros


def normalizar_data(valor: Any) -> date | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    return date.fromisoformat(texto)


def normalizar_inteiro(valor: Any) -> int | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    return int(texto)


def normalizar_decimal_cvm(valor: Any) -> Decimal | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    texto = texto.replace(".", "").replace(",", ".")
    return Decimal(texto)


def normalizar_conta_fixa(valor: Any) -> bool | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    if texto.upper() in {"S", "SIM", "TRUE", "1"}:
        return True
    if texto.upper() in {"N", "NAO", "NÃO", "FALSE", "0"}:
        return False
    raise ValueError(f"Valor invalido para conta_fixa: {valor}")


def _normalizar_canonico(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {chave: _normalizar_canonico(valor[chave]) for chave in sorted(valor)}
    if isinstance(valor, list):
        return [_normalizar_canonico(item) for item in valor]
    if isinstance(valor, str):
        texto = normalizar_texto(valor)
        if texto is None:
            return None
        texto_ascii = unicodedata.normalize("NFKC", texto)
        return texto_ascii
    return valor


def gerar_hash_canonico(dados: dict[str, Any], campos_ignorados: set[str] | None = None) -> str:
    campos_ignorados = campos_ignorados or set()
    payload = {k: v for k, v in dados.items() if k not in campos_ignorados}
    normalizado = _normalizar_canonico(payload)
    texto = json.dumps(normalizado, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def normalizar_linha_cadastro(
    linha: dict[str, Any],
    *,
    arquivo_origem: str,
    ano_origem: int | None,
    linha_origem: int,
) -> dict[str, Any]:
    endereco = {
        "tipo_endereco": normalizar_texto(linha.get("TP_ENDER")),
        "logradouro": normalizar_texto(linha.get("LOGRADOURO")),
        "complemento": normalizar_texto(linha.get("COMPL")),
        "bairro": normalizar_texto(linha.get("BAIRRO")),
        "municipio": normalizar_texto(linha.get("MUN")),
        "uf": normalizar_texto(linha.get("UF")),
        "pais": normalizar_texto(linha.get("PAIS")),
        "cep": normalizar_texto(linha.get("CEP")),
        "ddd_telefone": normalizar_texto(linha.get("DDD_TEL")),
        "telefone": normalizar_texto(linha.get("TEL")),
        "ddd_fax": normalizar_texto(linha.get("DDD_FAX")),
        "fax": normalizar_texto(linha.get("FAX")),
        "email": normalizar_texto(linha.get("EMAIL")),
    }

    data_inicio_responsavel = normalizar_data(linha.get("DT_INI_RESP"))
    responsavel = {
        "tipo_responsavel": normalizar_texto(linha.get("TP_RESP")),
        "nome_responsavel": normalizar_texto(linha.get("RESP")),
        "data_inicio_responsavel": (
            data_inicio_responsavel.isoformat() if data_inicio_responsavel is not None else None
        ),
        "logradouro": normalizar_texto(linha.get("LOGRADOURO_RESP")),
        "complemento": normalizar_texto(linha.get("COMPL_RESP")),
        "bairro": normalizar_texto(linha.get("BAIRRO_RESP")),
        "municipio": normalizar_texto(linha.get("MUN_RESP")),
        "uf": normalizar_texto(linha.get("UF_RESP")),
        "pais": normalizar_texto(linha.get("PAIS_RESP")),
        "cep": normalizar_texto(linha.get("CEP_RESP")),
        "ddd_telefone": normalizar_texto(linha.get("DDD_TEL_RESP")),
        "telefone": normalizar_texto(linha.get("TEL_RESP")),
        "ddd_fax": normalizar_texto(linha.get("DDD_FAX_RESP")),
        "fax": normalizar_texto(linha.get("FAX_RESP")),
        "email": normalizar_texto(linha.get("EMAIL_RESP")),
    }

    dados = {
        "cnpj_companhia": normalizar_cnpj(str(linha.get("CNPJ_CIA", ""))),
        "codigo_cvm": normalizar_inteiro(linha.get("CD_CVM")),
        "denominacao_social": normalizar_texto(linha.get("DENOM_SOCIAL")),
        "denominacao_comercial": normalizar_texto(linha.get("DENOM_COMERC")),
        "situacao_registro": normalizar_texto(linha.get("SIT")),
        "data_registro": normalizar_data(linha.get("DT_REG")),
        "data_constituicao": normalizar_data(linha.get("DT_CONST")),
        "data_cancelamento": normalizar_data(linha.get("DT_CANCEL")),
        "motivo_cancelamento": normalizar_texto(linha.get("MOTIVO_CANCEL")),
        "data_inicio_situacao": normalizar_data(linha.get("DT_INI_SIT")),
        "setor_atividade": normalizar_texto(linha.get("SETOR_ATIV")),
        "tipo_mercado": normalizar_texto(linha.get("TP_MERC")),
        "categoria_registro": normalizar_texto(linha.get("CATEG_REG")),
        "data_inicio_categoria": normalizar_data(linha.get("DT_INI_CATEG")),
        "situacao_emissor": normalizar_texto(linha.get("SIT_EMISSOR")),
        "data_inicio_situacao_emissor": normalizar_data(linha.get("DT_INI_SIT_EMISSOR")),
        "controle_acionario": normalizar_texto(linha.get("CONTROLE_ACIONARIO")),
        "endereco": endereco,
        "responsavel": responsavel,
        "auditor": normalizar_texto(linha.get("AUDITOR")),
        "cnpj_auditor": (
            normalizar_cnpj(str(linha["CNPJ_AUDITOR"])) if normalizar_texto(linha.get("CNPJ_AUDITOR")) else None
        ),
        "arquivo_origem": arquivo_origem,
        "ano_origem": ano_origem,
        "linha_origem": linha_origem,
    }

    dados["hash_origem"] = gerar_hash_canonico(
        dados,
        campos_ignorados={"hash_origem", "linha_origem"},
    )
    return dados

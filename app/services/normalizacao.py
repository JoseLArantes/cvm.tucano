import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any

_UF_POR_NOME: dict[str, str] = {
    "ACRE": "AC",
    "ALAGOAS": "AL",
    "AMAPA": "AP",
    "AMAZONAS": "AM",
    "BAHIA": "BA",
    "CEARA": "CE",
    "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES",
    "GOIAS": "GO",
    "MARANHAO": "MA",
    "MATO GROSSO": "MT",
    "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG",
    "PARA": "PA",
    "PARAIBA": "PB",
    "PARANA": "PR",
    "PERNAMBUCO": "PE",
    "PIAUI": "PI",
    "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO",
    "RORAIMA": "RR",
    "SANTA CATARINA": "SC",
    "SAO PAULO": "SP",
    "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


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
    try:
        return int(texto)
    except ValueError:
        dec_val = normalizar_decimal_cvm(texto)
        if dec_val is not None:
            return int(round(dec_val))
        return None


def normalizar_decimal_cvm(valor: Any) -> Decimal | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
        
    if texto.upper() in {"-", "N/A", "ND", "N/D", "NI", "NA", "N.A.", "N.A"}:
        return None

    # Detect and reject narrative descriptions (non-numeric text strings)
    # 1. Remove currency symbols and codes
    limpo = re.sub(r"(?i)\b(USD|BRL|EUR|GPB|CAD|AUD|CHF|JPY|CNY)\b|R\$|\$", "", texto)
    # 2. Remove digits, common signs, spaces, and punctuation
    limpo = re.sub(r"[\d.,\-+%\s\(\):/\\_]", "", limpo)
    # 3. Remove currency code letters to be tolerant to minor spacing/typos
    limpo = re.sub(r"(?i)[bdelrsu]", "", limpo)
    # 4. If any alphabetical characters remain, it is a narrative description and not a number
    if any(c.isalpha() for c in limpo):
        raise ValueError(f"Valor decimal invalido (narrativa detectada): {valor}")

    texto = re.sub(r"[^\d.,\-]", "", texto).strip()

    if not texto or texto == "-" or texto == "." or texto == ",":
        return None

    has_comma = "," in texto
    has_dot = "." in texto
    
    if has_comma and has_dot:
        last_comma = texto.rfind(",")
        last_dot = texto.rfind(".")
        if last_comma > last_dot:
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif has_comma:
        texto = texto.replace(",", ".")
    elif has_dot:
        if texto.count(".") > 1:
            texto = texto.replace(".", "")

    try:
        return Decimal(texto)
    except Exception as exc:
        raise ValueError(f"Valor decimal invalido: {valor}") from exc


def decimal_para_canonical_string(valor: Decimal | None) -> str | None:
    if valor is None:
        return None
    texto = format(valor, "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    if texto in {"", "-0"}:
        return "0"
    return texto


def data_para_string_br(valor: date | None) -> str | None:
    if valor is None:
        return None
    return valor.strftime("%d/%m/%Y")


def datetime_para_string_br(valor: datetime | None) -> str | None:
    if valor is None:
        return None
    return valor.strftime("%d/%m/%Y %H:%M:%S")


def normalizar_conta_fixa(valor: Any) -> bool | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    if texto.upper() in {"S", "SIM", "TRUE", "1"}:
        return True
    if texto.upper() in {"N", "NAO", "NÃO", "FALSE", "0"}:
        return False
    raise ValueError(f"Valor invalido para conta_fixa: {valor}")


def normalizar_sigla_uf(valor: Any) -> str | None:
    texto = normalizar_texto(valor)
    if texto is None:
        return None
    canonico = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").upper()
    if canonico in {"EXTERIOR", "ESTRANGEIRO", "INTERNACIONAL"}:
        return None
    if canonico in _UF_POR_NOME:
        return _UF_POR_NOME[canonico]
    if re.fullmatch(r"[A-Z]{2}", canonico):
        return canonico
    if len(canonico) <= 5:
        return canonico
    return None


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

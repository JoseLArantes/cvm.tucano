from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.ingestion.normalizers import normalizar_cnpj_opcional


def cnpj_tem_digitos_validos(valor: str | None) -> bool:
    if valor is None:
        return False
    numeros = re.sub(r"[^0-9]", "", valor)
    if len(numeros) != 14 or len(set(numeros)) == 1:
        return False

    base = numeros[:12]
    pesos_primeiro_digito = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    pesos_segundo_digito = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

    def calcular_digito(digitos: str, pesos: tuple[int, ...]) -> str:
        resto = sum(int(digito) * peso for digito, peso in zip(digitos, pesos, strict=True)) % 11
        return "0" if resto < 2 else str(11 - resto)

    primeiro = calcular_digito(base, pesos_primeiro_digito)
    segundo = calcular_digito(base + primeiro, pesos_segundo_digito)
    return numeros[-2:] == primeiro + segundo


@dataclass(frozen=True)
class CorrecaoCnpjCadastro:
    arquivo_origem: str
    codigo_cvm: int
    cnpj_origem: str
    denominacao_social: str
    cnpj_canonico: str
    regra: str
    evidencia: str
    evidencia_url: str


# The CVM foreign-company CSV has carried an invalid CNPJ for this registration.
# The replacement is supported by a CARF/RFB decision identifying Brazil Fast
# Food Corp. with CNPJ 05.714.446/0001-00. Keep the match exact and reviewable.
_CORRECOES_CNPJ_CADASTRO = (
    CorrecaoCnpjCadastro(
        arquivo_origem="cad_cia_estrang.csv",
        codigo_cvm=80012,
        cnpj_origem="05714446000400",
        denominacao_social="BRAZIL FAST FOOD CORP.",
        cnpj_canonico="05714446000100",
        regra="cvm-80012-brazil-fast-food-cnpj-carf",
        evidencia=(
            "Decisao CARF/RFB de 2016 identifica BRAZIL FAST FOOD CORP. "
            "pelo CNPJ 05.714.446/0001-00."
        ),
        evidencia_url=(
            "https://acordaos.economia.gov.br/solr/acordaos2_shard7_replica_n101/browse"
            "?debugQuery=true&fq=ano_sessao_s%3A%222016%22"
            "&fq=decisao_txt%3A%22a%22&fq=decisao_txt%3A%22do%22"
            "&fq=decisao_txt%3A%22em%22&fq=decisao_txt%3A%22membros%22"
            "&fq=nome_relator_s%3A%22FERNANDO+BRASIL+DE+OLIVEIRA+PINTO%22"
            "&fq=secao_s%3A%22Primeira+Se%C3%A7%C3%A3o+de+Julgamento%22&q="
        ),
    ),
)


@dataclass(frozen=True)
class ResolucaoCnpjCadastro:
    cnpj_canonico: str | None
    cnpj_origem: str | None
    diagnostico: dict[str, Any] | None = None


def resolver_cnpj_cadastro(
    valor: Any,
    *,
    arquivo_origem: str,
    linha_origem: int,
    codigo_cvm: int | None,
    denominacao_social: str | None,
) -> ResolucaoCnpjCadastro:
    cnpj_origem = normalizar_cnpj_opcional(valor)
    if cnpj_origem is None or cnpj_tem_digitos_validos(cnpj_origem):
        return ResolucaoCnpjCadastro(cnpj_canonico=cnpj_origem, cnpj_origem=cnpj_origem)

    nome = " ".join((denominacao_social or "").strip().upper().split())
    arquivo = Path(arquivo_origem).name
    correcao = next(
        (
            item
            for item in _CORRECOES_CNPJ_CADASTRO
            if item.arquivo_origem == arquivo
            and item.codigo_cvm == codigo_cvm
            and item.cnpj_origem == cnpj_origem
            and item.denominacao_social == nome
        ),
        None,
    )

    if correcao is not None:
        if not cnpj_tem_digitos_validos(correcao.cnpj_canonico):
            raise ValueError(f"CNPJ canônico inválido na regra {correcao.regra}.")
        return ResolucaoCnpjCadastro(
            cnpj_canonico=correcao.cnpj_canonico,
            cnpj_origem=cnpj_origem,
            diagnostico={
                "codigo_cvm": codigo_cvm,
                "arquivo_origem": arquivo,
                "linha_origem": linha_origem,
                "cnpj_origem": cnpj_origem,
                "cnpj_canonico": correcao.cnpj_canonico,
                "motivo": "digitos_verificadores_invalidos",
                "correcao_aplicada": True,
                "regra": correcao.regra,
                "evidencia": correcao.evidencia,
                "evidencia_url": correcao.evidencia_url,
            },
        )

    return ResolucaoCnpjCadastro(
        cnpj_canonico=None,
        cnpj_origem=cnpj_origem,
        diagnostico={
            "codigo_cvm": codigo_cvm,
            "arquivo_origem": arquivo,
            "linha_origem": linha_origem,
            "cnpj_origem": cnpj_origem,
            "cnpj_canonico": None,
            "motivo": "digitos_verificadores_invalidos",
            "correcao_aplicada": False,
            "regra": None,
            "evidencia": None,
            "evidencia_url": None,
        },
    )

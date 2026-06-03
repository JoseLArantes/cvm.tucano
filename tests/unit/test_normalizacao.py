from decimal import Decimal

from app.services.normalizacao import (
    normalizar_conta_fixa,
    normalizar_decimal_cvm,
    normalizar_linha_cadastro,
)


def test_normaliza_cnpj_cadastro() -> None:
    linha = {
        "CNPJ_CIA": "08.773.135/0001-00",
        "CD_CVM": "25224",
    }
    dados = normalizar_linha_cadastro(
        linha,
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
    )
    assert dados["cnpj_companhia"] == "08773135000100"


def test_data_vazia_gera_none() -> None:
    linha = {"CNPJ_CIA": "08.773.135/0001-00", "DT_CANCEL": ""}
    dados = normalizar_linha_cadastro(
        linha,
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
    )
    assert dados["data_cancelamento"] is None


def test_decimal_cvm() -> None:
    assert normalizar_decimal_cvm("1.234,56") == Decimal("1234.56")


def test_conta_fixa_booleano() -> None:
    assert normalizar_conta_fixa("S") is True
    assert normalizar_conta_fixa("N") is False

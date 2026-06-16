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
    import pytest
    assert normalizar_decimal_cvm("1.234,56") == Decimal("1234.56")
    assert normalizar_decimal_cvm("R$ 1.234,56") == Decimal("1234.56")
    assert normalizar_decimal_cvm("1,000.50") == Decimal("1000.50")
    assert normalizar_decimal_cvm("1%") == Decimal("1")
    assert normalizar_decimal_cvm("-10,00%") == Decimal("-10")
    assert normalizar_decimal_cvm("N/A") is None
    
    # Narratives should raise ValueError
    with pytest.raises(ValueError, match="narrativa detectada"):
        normalizar_decimal_cvm("O montante total da remuneração foi de R$ 17,574 milhões.")


def test_conta_fixa_booleano() -> None:
    assert normalizar_conta_fixa("S") is True
    assert normalizar_conta_fixa("N") is False

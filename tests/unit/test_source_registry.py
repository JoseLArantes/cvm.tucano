from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.source_registry import (
    dataset_por_member_name,
    dataset_por_row_kind,
    fontes_implementadas,
    listar_datasets,
    listar_fontes,
    obter_fonte,
)


def test_registry_contains_expected_sources_and_order() -> None:
    fontes = listar_fontes()
    assert [item.fonte for item in fontes] == [
        "cadastro", "dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"
    ]
    assert [item.fonte for item in fontes_implementadas()] == [
        "cadastro", "dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"
    ]


def test_registry_covers_datasets_for_supported_sources() -> None:
    assert obter_fonte("cadastro") is not None
    assert obter_fonte("dfp") is not None
    assert obter_fonte("itr") is not None
    assert obter_fonte("fre") is not None
    assert obter_fonte("fca") is not None
    assert obter_fonte("ipe") is not None

    fre = obter_fonte("fre")
    assert fre is not None
    assert fre.dependencias == ("cadastro",)
    assert fre.datasets_opcionais == 56
    assert any(item.dataset == "empregado_posicao_genero" and not item.obrigatorio for item in fre.datasets)

    fca = obter_fonte("fca")
    assert fca is not None
    assert fca.primeiro_ano == 2010
    assert fca.dependencias == ("cadastro",)
    assert fca.datasets_obrigatorios == 1
    assert fca.datasets_opcionais == 9
    assert {item.dataset for item in fca.datasets} == {
        "original",
        "geral",
        "endereco",
        "dri",
        "auditor",
        "valor_mobiliario",
        "escriturador",
        "canal_divulgacao",
        "departamento_acionistas",
        "pais_estrangeiro_negociacao",
    }

    ipe = obter_fonte("ipe")
    assert ipe is not None
    assert ipe.primeiro_ano == 2003
    assert ipe.dependencias == ("cadastro",)
    assert ipe.datasets_obrigatorios == 1
    assert ipe.datasets_opcionais == 0
    assert {item.dataset for item in ipe.datasets} == {"original"}

    vlmo = obter_fonte("vlmo")
    assert vlmo is not None
    assert vlmo.primeiro_ano == 2018
    assert vlmo.dependencias == ("cadastro",)
    assert vlmo.datasets_obrigatorios == 2
    assert vlmo.datasets_opcionais == 0
    assert {item.dataset for item in vlmo.datasets} == {"original", "consolidado"}

    cgvn = obter_fonte("cgvn")
    assert cgvn is not None
    assert cgvn.primeiro_ano == 2018
    assert cgvn.dependencias == ("cadastro",)
    assert cgvn.datasets_obrigatorios == 2
    assert cgvn.datasets_opcionais == 0
    assert {item.dataset for item in cgvn.datasets} == {"original", "praticas"}


def test_registry_covers_all_financeiro_demonstration_members() -> None:
    for fonte in ("dfp", "itr"):
        datasets = listar_datasets(fonte)
        rendered = {item.render_member_name(ano=2025) for item in datasets}
        assert f"{fonte}_cia_aberta_2025.csv" in rendered
        assert f"{fonte}_cia_aberta_composicao_capital_2025.csv" in rendered
        assert f"{fonte}_cia_aberta_parecer_2025.csv" in rendered
        for nome_arquivo, _, _ in arquivos_demonstracao(fonte, 2025):
            assert nome_arquivo in rendered


def test_registry_dataset_lookup_by_member_name_and_row_kind() -> None:
    dataset = dataset_por_member_name("fre", "fre_cia_aberta_auditor_2025.csv", 2025)
    assert dataset is not None
    assert dataset.row_kind == "fre_auditor"

    dataset = dataset_por_row_kind("dfp_documento")
    assert dataset is not None
    assert dataset.dataset == "documento_principal"

    dataset = dataset_por_member_name("fca", "fca_cia_aberta_geral_2025.csv", 2025)
    assert dataset is not None
    assert dataset.row_kind == "fca_geral"

    dataset = dataset_por_member_name("ipe", "ipe_cia_aberta_2025.csv", 2025)
    assert dataset is not None
    assert dataset.row_kind == "ipe_documento"

    dataset = dataset_por_member_name("vlmo", "vlmo_cia_aberta_con_2025.csv", 2025)
    assert dataset is not None
    assert dataset.row_kind == "vlmo_consolidado"


def test_registry_dependency_graph() -> None:
    cadastro = obter_fonte("cadastro")
    dfp = obter_fonte("dfp")
    itr = obter_fonte("itr")
    fre = obter_fonte("fre")
    fca = obter_fonte("fca")
    ipe = obter_fonte("ipe")
    vlmo = obter_fonte("vlmo")
    cgvn = obter_fonte("cgvn")

    assert cadastro is not None and cadastro.dependencias == ()
    assert dfp is not None and dfp.dependencias == ("cadastro",)
    assert itr is not None and itr.dependencias == ("cadastro",)
    assert fre is not None and fre.dependencias == ("cadastro",)
    assert fca is not None and fca.dependencias == ("cadastro",)
    assert ipe is not None and ipe.dependencias == ("cadastro",)
    assert vlmo is not None and vlmo.dependencias == ("cadastro",)
    assert cgvn is not None and cgvn.dependencias == ("cadastro",)


def test_registry_coverage_guards_for_current_sources() -> None:
    row_kinds = {
        "cadastro_registro_cvm",
        "dfp_documento",
        "dfp_demonstracao",
        "dfp_composicao_capital",
        "dfp_parecer",
        "itr_documento",
        "itr_demonstracao",
        "itr_composicao_capital",
        "itr_parecer",
        "fre_documento",
        "fre_auditor",
        "fre_capital_social",
        "fre_posicao_acionaria",
        "fre_remuneracao_total_orgao",
        "fre_participacao_sociedade",
        "fre_empregado_posicao_genero",
        "fre_empregado_posicao_local",
        "fre_empregado_posicao_faixa_etaria",
        "fre_empregado_posicao_declaracao_raca",
        "fre_empregado_pcd",
        "fre_empregado_local_faixa_etaria",
        "fre_empregado_local_declaracao_raca",
        "fre_empregado_local_declaracao_genero",
        "fre_responsavel",
        "fre_capital_social_classe_acao",
        "fre_capital_social_titulo_conversivel",
        "fre_distribuicao_capital",
        "fre_distribuicao_capital_classe_acao",
        "fre_posicao_acionaria_classe_acao",
        "fre_remuneracao_maxima_minima_media",
        "fre_remuneracao_variavel",
        "fre_remuneracao_acao",
        "fre_acao_entregue",
        "fre_administrador_membro_conselho_fiscal",
        "fre_membro_comite",
        "fre_relacao_familiar",
        "fre_relacao_subordinacao",
        "fre_transacao_parte_relacionada",
        "fre_capital_social_aumento",
        "fre_capital_social_aumento_classe_acao",
        "fre_capital_social_desdobramento",
        "fre_capital_social_desdobramento_classe_acao",
        "fre_capital_social_reducao",
        "fre_capital_social_reducao_classe_acao",
        "fre_direito_acao",
        "fre_volume_valor_mobiliario",
        "fre_outro_valor_mobiliario",
        "fre_titular_valor_mobiliario",
        "fre_mercado_estrangeiro",
        "fre_titulo_exterior",
        "fre_plano_recompra",
        "fre_plano_recompra_classe_acao",
        "fre_valor_mobiliario_tesouraria_movimentacao",
        "fre_valor_mobiliario_tesouraria_ultimo_exercicio",
        "fre_administrador_pcd",
        "fre_administrador_declaracao_genero",
        "fre_administrador_declaracao_raca",
        "fca_documento",
        "fca_geral",
        "fca_endereco",
        "fca_dri",
        "fca_auditor",
        "fca_valor_mobiliario",
        "fca_escriturador",
        "fca_canal_divulgacao",
        "fca_departamento_acionistas",
        "fca_pais_estrangeiro_negociacao",
        "ipe_documento",
        "vlmo_documento",
        "vlmo_consolidado",
        "cgvn_documento",
        "cgvn_pratica",
    }
    for row_kind in row_kinds:
        assert dataset_por_row_kind(row_kind) is not None

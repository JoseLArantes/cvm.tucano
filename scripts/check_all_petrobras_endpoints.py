from __future__ import annotations

import sys
from typing import Any

from fastapi.testclient import TestClient

sys.path.append("/app")

from app.core.config import get_settings
from app.main import app

settings = get_settings()
client = TestClient(app)
headers = {"Authorization": f"Bearer {settings.api_token}"}

ENDPOINTS: list[tuple[str, str, dict[str, Any], str]] = [
    ("obter_companhia_por_codigo_cvm", "/companhias/codigo-cvm/9512", {}, "Cadastro"),
    ("obter_companhia_por_cnpj", "/companhias/33000167000101", {}, "Cadastro"),
    ("listar_companhias", "/companhias", {"codigo_cvm": 9512}, "Cadastro"),
    ("listar_documentos_dfp", "/dfp/documentos", {"codigo_cvm": 9512}, "DFP"),
    ("listar_composicao_capital_dfp", "/dfp/composicao-capital", {"codigo_cvm": 9512}, "DFP"),
    ("listar_pareceres_dfp", "/dfp/pareceres", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_bpa_con", "/dfp/balanco-patrimonial-ativo/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_bpa_ind", "/dfp/balanco-patrimonial-ativo/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_bpp_con", "/dfp/balanco-patrimonial-passivo/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_bpp_ind", "/dfp/balanco-patrimonial-passivo/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dfc_md_con", "/dfp/fluxo-caixa-metodo-direto/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dfc_md_ind", "/dfp/fluxo-caixa-metodo-direto/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dfc_mi_con", "/dfp/fluxo-caixa-metodo-indireto/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dfc_mi_ind", "/dfp/fluxo-caixa-metodo-indireto/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dmpl_con", "/dfp/mutacoes-patrimonio-liquido/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dmpl_ind", "/dfp/mutacoes-patrimonio-liquido/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dra_con", "/dfp/resultado-abrangente/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dra_ind", "/dfp/resultado-abrangente/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dre_con", "/dfp/demonstracao-resultado/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dre_ind", "/dfp/demonstracao-resultado/individual", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dva_con", "/dfp/valor-adicionado/consolidado", {"codigo_cvm": 9512}, "DFP"),
    ("dfp_dva_ind", "/dfp/valor-adicionado/individual", {"codigo_cvm": 9512}, "DFP"),
    ("listar_documentos_itr", "/itr/documentos", {"codigo_cvm": 9512}, "ITR"),
    ("listar_composicao_capital_itr", "/itr/composicao-capital", {"codigo_cvm": 9512}, "ITR"),
    ("listar_pareceres_itr", "/itr/pareceres", {"codigo_cvm": 9512}, "ITR"),
    ("itr_bpa_con", "/itr/balanco-patrimonial-ativo/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_bpa_ind", "/itr/balanco-patrimonial-ativo/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_bpp_con", "/itr/balanco-patrimonial-passivo/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_bpp_ind", "/itr/balanco-patrimonial-passivo/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dfc_md_con", "/itr/fluxo-caixa-metodo-direto/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dfc_md_ind", "/itr/fluxo-caixa-metodo-direto/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dfc_mi_con", "/itr/fluxo-caixa-metodo-indireto/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dfc_mi_ind", "/itr/fluxo-caixa-metodo-indireto/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dmpl_con", "/itr/mutacoes-patrimonio-liquido/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dmpl_ind", "/itr/mutacoes-patrimonio-liquido/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dra_con", "/itr/resultado-abrangente/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dra_ind", "/itr/resultado-abrangente/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dre_con", "/itr/demonstracao-resultado/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dre_ind", "/itr/demonstracao-resultado/individual", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dva_con", "/itr/valor-adicionado/consolidado", {"codigo_cvm": 9512}, "ITR"),
    ("itr_dva_ind", "/itr/valor-adicionado/individual", {"codigo_cvm": 9512}, "ITR"),
    ("listar_documentos_fca", "/fca/documentos", {"codigo_cvm": 9512}, "FCA"),
    ("listar_geral_fca", "/fca/geral", {"codigo_cvm": 9512}, "FCA"),
    ("listar_enderecos_fca", "/fca/enderecos", {"codigo_cvm": 9512}, "FCA"),
    ("listar_dri_fca", "/fca/dri", {"codigo_cvm": 9512}, "FCA"),
    ("listar_auditores_fca", "/fca/auditores", {"codigo_cvm": 9512}, "FCA"),
    ("listar_valores_mobiliarios_fca", "/fca/valores-mobiliarios", {"codigo_cvm": 9512}, "FCA"),
    ("listar_documentos_fre", "/fre/documentos", {"codigo_cvm": 9512}, "FRE"),
    ("listar_auditores_fre", "/fre/auditores", {"codigo_cvm": 9512}, "FRE"),
    ("listar_capital_social_fre", "/fre/capital-social", {"codigo_cvm": 9512}, "FRE"),
    ("listar_posicao_acionaria_fre", "/fre/posicao-acionaria", {"codigo_cvm": 9512}, "FRE"),
    ("listar_remuneracao_total_orgao_fre", "/fre/remuneracao/total-por-orgao", {"codigo_cvm": 9512}, "FRE"),
    ("listar_empregado_posicao_genero_fre", "/fre/empregados/posicao-genero", {"codigo_cvm": 9512}, "FRE"),
    ("listar_responsaveis_fre", "/fre/responsaveis", {"codigo_cvm": 9512}, "FRE"),
    ("listar_capital_social_classes_acoes_fre", "/fre/capital-social-classes-acoes", {"codigo_cvm": 9512}, "FRE"),
    (
        "listar_capital_social_titulos_conversiveis_fre",
        "/fre/capital-social-titulos-conversiveis",
        {"codigo_cvm": 9512},
        "FRE",
    ),
    ("listar_distribuicao_capital_fre", "/fre/distribuicao-capital", {"codigo_cvm": 9512}, "FRE"),
    (
        "listar_distribuicao_capital_classes_acoes_fre",
        "/fre/distribuicao-capital-classes-acoes",
        {"codigo_cvm": 9512},
        "FRE",
    ),
    (
        "listar_posicoes_acionarias_classes_acoes_fre",
        "/fre/posicoes-acionarias-classes-acoes",
        {"codigo_cvm": 9512},
        "FRE",
    ),
    (
        "listar_remuneracoes_maximas_minimas_medias_fre",
        "/fre/remuneracoes-maximas-minimas-medias",
        {"codigo_cvm": 9512},
        "FRE",
    ),
    ("listar_remuneracoes_variaveis_fre", "/fre/remuneracoes-variaveis", {"codigo_cvm": 9512}, "FRE"),
    ("listar_remuneracoes_acoes_fre", "/fre/remuneracoes-acoes", {"codigo_cvm": 9512}, "FRE"),
    ("listar_acoes_entregues_fre", "/fre/acoes-entregues", {"codigo_cvm": 9512}, "FRE"),
    ("listar_documentos_ipe", "/ipe/documentos", {"codigo_cvm": 9512}, "IPE"),
    ("listar_documentos_vlmo", "/vlmo/documentos", {"codigo_cvm": 9512}, "VLMO"),
    ("listar_consolidado_vlmo", "/vlmo/consolidado", {"codigo_cvm": 9512}, "VLMO"),
    ("listar_documentos_cgvn", "/cgvn/documentos", {"codigo_cvm": 9512}, "CGVN"),
    ("listar_praticas_cgvn", "/cgvn/praticas", {"codigo_cvm": 9512}, "CGVN"),
    ("listar_fontes", "/fontes", {}, "Exportacao"),
    ("listar_datasets", "/fontes/dfp/datasets", {}, "Exportacao"),
    ("exportar_documento_principal", "/exportacoes/dfp/documento_principal", {"codigo_cvm": 9512}, "Exportacao"),
    ("exportar_bpa_ind", "/exportacoes/dfp/bpa_ind", {"codigo_cvm": 9512}, "Exportacao"),
    ("consultar_companhia_mestre", "/companhias/mestre", {"codigo_cvm": 9512}, "Mestre"),
    ("consultar_companhia_mestre_cnpj", "/companhias/mestre", {"codigo_cvm": 9512}, "Mestre"),
    ("health", "/health", {}, "Health"),
]


def _record_count(body: Any) -> int:
    if isinstance(body, dict):
        if "dados" in body and isinstance(body["dados"], list):
            return len(body["dados"])
        if "id" in body:
            return 1
        return 0
    if isinstance(body, list):
        return len(body)
    return 0


def main() -> None:
    results: list[dict[str, Any]] = []
    for name, path, params, category in ENDPOINTS:
        try:
            response = client.get(path, params=params, headers=headers)
            try:
                body: Any = response.json()
            except Exception:
                body = {}
            results.append(
                {
                    "name": name,
                    "path": path,
                    "params": params,
                    "category": category,
                    "status_code": response.status_code,
                    "records_count": _record_count(body),
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "name": name,
                    "path": path,
                    "params": params,
                    "category": category,
                    "status_code": 500,
                    "records_count": 0,
                    "error": str(exc),
                }
            )

    for category in sorted({item["category"] for item in results}):
        print(f"\n=== Categoria: {category} ===")
        print(f"{'Endpoint Name':<45} | {'Path':<50} | {'Status':<6} | {'Count':<6} | {'Gaps/Issues'}")
        print("-" * 140)
        for item in [entry for entry in results if entry["category"] == category]:
            issue = ""
            if item["status_code"] != 200:
                issue = f"HTTP {item['status_code']}: {item['error'] or 'Failure'}"
            elif item["records_count"] == 0 and category not in ("Exportacao", "Cadastro"):
                issue = "No data returned (Possibly not synced or table empty)"
            print(
                f"{item['name']:<45} | {item['path']:<50} | "
                f"{item['status_code']:<6} | {item['records_count']:<6} | {issue}"
            )


if __name__ == "__main__":
    main()

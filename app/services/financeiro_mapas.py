from collections.abc import Iterable

ESCOPOS_DEMONSTRACAO = {"con": "consolidado", "ind": "individual"}

DEMONSTRACOES = [
    {"codigo": "BPA", "tipo": "balanco_patrimonial_ativo", "rota": "balanco-patrimonial-ativo"},
    {"codigo": "BPP", "tipo": "balanco_patrimonial_passivo", "rota": "balanco-patrimonial-passivo"},
    {"codigo": "DFC_MD", "tipo": "fluxo_caixa_metodo_direto", "rota": "fluxo-caixa-metodo-direto"},
    {"codigo": "DFC_MI", "tipo": "fluxo_caixa_metodo_indireto", "rota": "fluxo-caixa-metodo-indireto"},
    {"codigo": "DMPL", "tipo": "mutacoes_patrimonio_liquido", "rota": "mutacoes-patrimonio-liquido"},
    {"codigo": "DRA", "tipo": "resultado_abrangente", "rota": "resultado-abrangente"},
    {"codigo": "DRE", "tipo": "demonstracao_resultado", "rota": "demonstracao-resultado"},
    {"codigo": "DVA", "tipo": "valor_adicionado", "rota": "valor-adicionado"},
]


def arquivos_demonstracao(prefixo: str, ano: int) -> Iterable[tuple[str, str, str]]:
    for item in DEMONSTRACOES:
        for escopo_codigo, escopo in ESCOPOS_DEMONSTRACAO.items():
            nome_arquivo = f"{prefixo}_cia_aberta_{item['codigo']}_{escopo_codigo}_{ano}.csv"
            yield nome_arquivo, item["tipo"], escopo

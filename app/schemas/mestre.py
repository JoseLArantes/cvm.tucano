from pydantic import BaseModel, Field

from app.schemas.companhia import CompanhiaResposta
from app.schemas.financeiro import (
    ListaComposicoesCapitalResposta,
    ListaDemonstracoesFinanceirasResposta,
    ListaDocumentosFinanceirosResposta,
    ListaPareceresFinanceirosResposta,
)
from app.schemas.fre import (
    ListaFreAuditoresResposta,
    ListaFreCapitalSocialResposta,
    ListaFreDocumentosResposta,
    ListaFreEmpregadoPosicaoGeneroResposta,
    ListaFrePosicaoAcionariaResposta,
    ListaFreRemuneracaoTotalOrgaoResposta,
)


class ConsultaCompanhiaMestreResposta(BaseModel):
    companhia: CompanhiaResposta = Field(description="Cadastro raiz da companhia consultada.")
    documentos_dfp: ListaDocumentosFinanceirosResposta = Field(description="Resultado de `GET /dfp/documentos`.")
    documentos_itr: ListaDocumentosFinanceirosResposta = Field(description="Resultado de `GET /itr/documentos`.")
    composicao_capital_dfp: ListaComposicoesCapitalResposta = Field(
        description="Resultado de `GET /dfp/composicao-capital`."
    )
    composicao_capital_itr: ListaComposicoesCapitalResposta = Field(
        description="Resultado de `GET /itr/composicao-capital`."
    )
    pareceres_dfp: ListaPareceresFinanceirosResposta = Field(description="Resultado de `GET /dfp/pareceres`.")
    pareceres_itr: ListaPareceresFinanceirosResposta = Field(description="Resultado de `GET /itr/pareceres`.")
    demonstracoes: dict[str, ListaDemonstracoesFinanceirasResposta] = Field(
        description=(
            "Mapa com todas as combinacoes de demonstracoes DFP/ITR por tipo e escopo. "
            "A chave segue o padrao `formulario_rota_escopo`."
        )
    )
    fre_documentos: ListaFreDocumentosResposta = Field(description="Resultado de `GET /fre/documentos`.")
    fre_auditores: ListaFreAuditoresResposta = Field(description="Resultado de `GET /fre/auditores`.")
    fre_capital_social: ListaFreCapitalSocialResposta = Field(description="Resultado de `GET /fre/capital-social`.")
    fre_posicao_acionaria: ListaFrePosicaoAcionariaResposta = Field(
        description="Resultado de `GET /fre/posicao-acionaria`."
    )
    fre_remuneracao_total_orgao: ListaFreRemuneracaoTotalOrgaoResposta = Field(
        description="Resultado de `GET /fre/remuneracao/total-por-orgao`."
    )
    fre_empregados_posicao_genero: ListaFreEmpregadoPosicaoGeneroResposta = Field(
        description="Resultado de `GET /fre/empregados/posicao-genero`."
    )

from fastapi import Depends, FastAPI

from app.api.auth import validar_token_api
from app.api.routers import protected_router, public_router
from app.core.config import get_settings
from app.core.observabilidade import ObservabilidadeMiddleware, configurar_logging, criar_app_metricas

DESCRICAO_API = """
API para normalização e consulta de dados públicos da CVM de companhias abertas.

Principais características desta versão:

1. Entidade raiz de companhias (`/companhias`) com campos em português.
2. Endpoints DFP e ITR separados por tipo documental e escopo.
3. Filtros padronizados por companhia, período, ano de origem e versão.
4. Paginação uniforme no formato `dados` + `paginacao`.
5. Endpoints administrativos para disparo e inspeção de sincronizações.

Regras operacionais relevantes:

- `sincronizado_em` pode mudar em toda sincronização.
- `alterado_em` muda apenas quando há alteração real de campo de negócio.
- Diferenças irrelevantes de formatação são normalizadas antes da comparação.
"""

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Autenticacao por usuario e senha para obtencao do token bearer.",
    },
    {
        "name": "health",
        "description": "Verificação simples de disponibilidade da API.",
    },
    {
        "name": "companhias",
        "description": "Consulta cadastral da entidade raiz `companhias`.",
    },
    {
        "name": "financeiro",
        "description": "Consultas DFP e ITR: documentos, demonstrações, composição de capital e pareceres.",
    },
    {
        "name": "mestre",
        "description": "Consulta agregada por companhia em todos os domínios documentais.",
    },
    {
        "name": "fre",
        "description": (
            "Consultas FRE MVP: documentos, auditores, capital social, "
            "posição acionária, remuneração e empregados."
        ),
    },
    {
        "name": "admin",
        "description": (
            "Operacoes administrativas de sincronizacao, monitoramento de execucao, "
            "quarentena v2, replay e rebuild de identidade."
        ),
    },
    {
        "name": "usuarios",
        "description": "Gestao de usuarios com login e controle administrativo.",
    },
]

app = FastAPI(
    title="API CVM Companhias Abertas",
    version="0.1.0",
    description=DESCRICAO_API,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=OPENAPI_TAGS,
)
settings = get_settings()
configurar_logging(settings.log_level)

app.add_middleware(ObservabilidadeMiddleware, habilitar_metricas=settings.enable_prometheus_metrics)
if settings.enable_prometheus_metrics:
    app_metricas = criar_app_metricas()
    if app_metricas is not None:
        app.mount("/metrics", app_metricas)

app.include_router(public_router)
app.include_router(protected_router, dependencies=[Depends(validar_token_api)])

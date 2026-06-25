from typing import Any, cast

from fastapi import Depends, FastAPI

from app.api.auth import validar_token_api
from app.api.routers import protected_router, public_router
from app.core.config import get_settings
from app.core.observabilidade import ObservabilidadeMiddleware, configurar_logging, criar_app_metricas

DESCRICAO_API = """
API para normalização e consulta de dados públicos da CVM de companhias abertas.

### Principais características desta versão:

1. Entidade raiz de companhias (`/companhias`) com campos em português.
2. Endpoints DFP e ITR separados por tipo documental e escopo.
3. Filtros padronizados por companhia, período, ano de origem e versão.
4. Paginação uniforme no formato `dados` + `paginacao`.
5. Endpoints administrativos para disparo e inspeção de sincronizações.

### Regras operacionais relevantes:

- `sincronizado_em` pode mudar em toda sincronização.
- `alterado_em` muda apenas quando há alteração real de campo de negócio.
- Diferenças irrelevantes de formatação são normalizadas antes da comparação.

### Fluxo de Ingestão em Duas Fases:

A ingestão de fontes de dados anuais (DFP, ITR, FRE, FCA, IPE, VLMO, CGVN) é executada em duas fases para otimizar o consumo de recursos e permitir inspeção intermediária:
- **Fase 1 (Pré-processamento):** Efetua o download do arquivo ZIP da CVM, verifica sua integridade (calcula o hash do arquivo) e realiza a extração/mapeamento de seus membros e metadados, registrando os arquivos na tabela de staging.
- **Fase 2 (Ingestão/Processamento):** Efetua a leitura real dos dados de cada arquivo membro para o banco de dados. Esta fase é paralelizada por meio de tarefas Celery executadas concorrentemente por múltiplas réplicas de workers.

### Comportamento do parâmetro `force_reimport`:

- **`force_reimport=false` (padrão):** O sistema utiliza otimização baseada em hash. Se o hash do arquivo a ser processado já estiver registrado no banco de dados e não houver sinalização de erro anterior, o reprocessamento é pulado para economizar recursos.
- **`force_reimport=true`:** O sistema força a re-ingestão total dos dados. Ele ignora a checagem de hash existente, realiza uma limpeza completa e atômica de dados antigos daquela execução de membro (linhas em staging, eventos e itens de quarentena associados) e re-executa a ingestão para garantir idempotência, evitando duplicações ou conflitos de chave única (`UniqueViolation`).

### Paralelismo e Execução de Workers Celery:

O pipeline está configurado para escalabilidade dinâmica com múltiplas instâncias de workers em execução. Para garantir distribuição justa de carga de trabalho de longa duração:
- O Celery utiliza prefetch desabilitado ou reduzido (`worker_prefetch_multiplier = 1` e opção `-Ofair`) garantindo que os workers não acumulem tarefas pré-alocadas na fila de mensagens local enquanto outros workers ficam ociosos.
- Os pipelines de ZIPs usam fluxos não-bloqueantes (`chain` e `chord`) para evitar deadlocks de workers aguardando a conclusão de subtarefas sincronamente.

### Serviço de Atualizações de Dados (Updates Service):

O Updates Service introduz um fluxo de detecção prévia (detection-first workflow) para separar a descoberta de dados da ingestão física:
- **Varredura Diária (Scanner):** Um job diário que executa solicitações rápidas HTTP HEAD nas URLs oficiais da CVM, gerando registros em `pending_updates` ao identificar modificações.
- **Análise Profunda (Deep Analysis):** Efetua download temporário de ZIPs/CSVs para calcular metadados e gerar relatórios de diferenças entre os dados membros novos e os metadados da última importação com sucesso.
- **Aprovação e Disparo Manual:** Bloqueia execuções automáticas de ingestão, as quais devem originar-se exclusivamente de chamadas explícitas nos endpoints de disparo (ou em lotes via sessões).

### Resiliência e Tentativas de Reprocessamento (Retries):

- Falhas transientes de rede ou conexão com o banco de dados provocam a retentativa automática das tarefas Celery.
- O mecanismo de limpeza atômica de staging é executado no início do processamento de cada membro de arquivo, garantindo que execuções parciais anteriores causadas por falhas de tarefas não deixem lixo que cause violações de restrição de chave no banco.
- O reprocessamento da quarentena é resiliente: falhas inesperadas no parsing ou validação de uma linha individual não abortam a execução em lote das demais linhas.
- Em dados estruturados da CVM, o parsing numérico trata `.` como separador decimal de máquina e não aceita separadores de milhares. Escalas monetárias (`UNIDADE`, `MIL`, `MILHAO`) são aplicadas apenas a partir do metadado explícito da CVM, nunca inferidas da pontuação.
- Na API, valores decimais são serializados como strings decimais canônicas, sem separadores de milhares. Localização brasileira (`1.234,56`) deve ser aplicada apenas na camada de apresentação do cliente.
"""

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Autenticação por usuário e senha para obtenção do token bearer.",
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
        "name": "analise",
        "description": (
            "API analítica orientada a períodos, métricas, comparabilidade, qualidade e evidências. "
            "Expõe manifesto, catálogo de métricas, séries, comparações, sinais, eventos e reapresentações."
        ),
    },
    {
        "name": "financeiro",
        "description": "Consultas DFP e ITR: documentos, demonstrações, composição de capital e pareceres.",
    },
    {
        "name": "fca",
        "description": "Consultas FCA: documentos, dados gerais, endereços, DRI, auditores e valores mobiliários.",
    },
    {
        "name": "ipe",
        "description": "Consultas IPE: documentos eventuais com filtros por companhia, período, categoria e assunto.",
    },
    {
        "name": "vlmo",
        "description": "Consultas VLMO: documentos e consolidado de valores mobiliários negociados e detidos.",
    },
    {
        "name": "cgvn",
        "description": "Consultas CGVN: documentos e práticas do Código Brasileiro de Governança Corporativa.",
    },
    {
        "name": "mestre",
        "description": "Consulta agregada por companhia em todos os domínios documentais.",
    },
    {
        "name": "fre",
        "description": (
            "Consultas FRE MVP: documentos, auditores, capital social, posição acionária, remuneração e empregados."
        ),
    },
    {
        "name": "ingestion",
        "description": (
            "Operações de ingestão de sincronização, monitoramento de execução, "
            "quarentena, replay e rebuild de identidade."
        ),
    },
    {
        "name": "usuarios",
        "description": "Gestão de usuários com login e controle administrativo.",
    },
    {
        "name": "fontes",
        "description": "Catálogo de fontes de dados e tabelas registradas no sistema.",
    },
    {
        "name": "exportacao",
        "description": "Exportações em lote e recuperação de dados CVM por filtros e formato (JSON/CSV).",
    },
    {
        "name": "updates",
        "description": "Gerenciamento e disparo manual de atualizações detectadas da CVM (Updates Service).",
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
        app.mount("/metrics", cast(Any, app_metricas))

app.include_router(public_router)
app.include_router(protected_router, dependencies=[Depends(validar_token_api)])

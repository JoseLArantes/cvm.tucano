---
title: Instalação e Configuração
sidebar_position: 1
---

# Instalação e Configuração

## Requisitos

- **Python** 3.12 ou superior
- **Docker** e **Docker Compose**
- **PostgreSQL** 16 (incluído no Docker Compose)
- **Redis** 7 (incluído no Docker Compose)

## Instalação Rápida

### 1. Clone o Repositório

```bash
git clone <repository-url>
cd tucano-cvm
```

### 2. Configure o Ambiente

Copie o arquivo de exemplo e ajuste as variáveis:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:

```bash
# Banco de dados
DATABASE_URL=postgresql://user:password@postgres:5432/tucano_cvm

# Redis
REDIS_URL=redis://redis:6379/0

# Token de sistema (use para bootstrap inicial)
TUCANO_CVM_TOKEN=seu-token-seguro-aqui

# URL base da CVM
CVM_BASE_URL=https://dados.cvm.gov.br

# Configurações de ingestão
INGESTION_V2_ENABLED=true
INGESTION_V2_PROMOTE_ENABLED=true

# Anos iniciais para sincronização
ANOS_INICIAIS_DFP=2020,2021,2022,2023,2024,2025
ANOS_INICIAIS_ITR=2020,2021,2022,2023,2024,2025
ANOS_INICIAIS_FRE=2020,2021,2022,2023,2024,2025
```

### 3. Inicie os Serviços

```bash
docker compose up --build
```

Isso iniciará:
- `cvm_api` - Servidor HTTP (porta 8000)
- `cvm_worker` - Celery worker (4 réplicas)
- `cvm_scheduler` - Celery beat
- `postgres` - Banco de dados PostgreSQL
- `redis` - Broker de mensagens

### 4. Execute as Migrações

```bash
docker compose run --rm cvm_api alembic upgrade head
```

### 5. Verifique a Saúde do Sistema

```bash
curl http://localhost:8007/health
```

Resposta esperada:
```json
{
  "status": "ok"
}
```

## Variáveis de Ambiente Importantes

### Banco de Dados e Infraestrutura

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | URL de conexão PostgreSQL | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | URL de conexão Redis | `redis://host:6379/0` |
| `LOG_LEVEL` | Nível de log | `INFO`, `DEBUG`, `WARNING` |
| `AMBIENTE` | Ambiente de execução | `development`, `production` |

### Autenticação

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `TUCANO_CVM_TOKEN` | Token de sistema para bootstrap | `token-seguro-aleatorio` |
| `ACCESS_TOKEN_TTL_MINUTES` | Tempo de vida do token (padrão: 480) | `480` |

### Ingestão

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `INGESTION_V2_ENABLED` | Habilita pipeline v2 | `true` |
| `INGESTION_V2_PROMOTE_ENABLED` | Habilita promoção para tabelas de domínio | `true` |
| `INGESTION_MAX_RETRIES` | Máximo de retentativas | `5` |
| `INGESTION_RETRY_BACKOFF_MAX_SECONDS` | Backoff máximo entre retentativas | `600` |
| `INGESTION_COMPANY_MISSING_MAX_RATIO` | Razão máxima de companhias não encontradas | `0.01` |
| `INGESTION_STAGE_BATCH_SIZE` | Linhas por batch durante stage | `5000` |
| `INGESTION_PROMOTE_BATCH_SIZE` | Linhas por batch durante promoção | `5000` |

### Anos Iniciais por Fonte

| Variável | Descrição |
|----------|-----------|
| `ANOS_INICIAIS_DFP` | Anos para sincronizar DFP |
| `ANOS_INICIAIS_ITR` | Anos para sincronizar ITR |
| `ANOS_INICIAIS_FRE` | Anos para sincronizar FRE |
| `ANOS_INICIAIS_FCA` | Anos para sincronizar FCA |
| `ANOS_INICIAIS_IPE` | Anos para sincronizar IPE |
| `ANOS_INICIAIS_VLMO` | Anos para sincronizar VLMO |
| `ANOS_INICIAIS_CGVN` | Anos para sincronizar CGVN |

Exemplo:
```bash
ANOS_INICIAIS_DFP=2020,2021,2022,2023,2024,2025
```

## Comandos Úteis

### Executar Testes

```bash
docker compose run --rm cvm_api python -m pytest -q
```

### Verificar Qualidade de Código

```bash
# Linting
docker compose run --rm cvm_api ruff check .

# Type checking
docker compose run --rm cvm_api mypy .
```

### Limpar Banco de Dados Local

```bash
./scripts/purge-local-db.sh --yes
```

### Acessar Logs

```bash
# Logs da API
docker compose logs -f cvm_api

# Logs dos workers
docker compose logs -f cvm_worker

# Logs do scheduler
docker compose logs -f cvm_scheduler
```

### Executar Migrações

```bash
# Aplicar migrações
docker compose run --rm cvm_api alembic upgrade head

# Reverter última migração
docker compose run --rm cvm_api alembic downgrade -1

# Ver status das migrações
docker compose run --rm cvm_api alembic current
```

## Estrutura de Diretórios

```
tucano-cvm/
├── app/
│   ├── api/              # Endpoints HTTP
│   ├── core/             # Configurações e dependências
│   ├── models/           # Modelos SQLAlchemy
│   ├── schemas/          # Schemas Pydantic
│   ├── services/         # Lógica de negócio
│   └── ingestion/        # Pipeline de ingestão
├── alembic/              # Migrações de banco
├── tests/                # Testes unitários e de integração
├── scripts/              # Scripts auxiliares
├── docker-compose.yml    # Serviços principais
└── docker-compose.workers.yml  # Workers e scheduler
```

## Próximos Passos

Após a instalação, consulte:

1. [Autenticação](./authentication.md) - Como autenticar na API
2. [Inicio Rapido](./quickstart.md) - Primeiras consultas
3. [Pipeline de Ingestão](../concepts/ingestion-pipeline.md) - Como funciona a ingestão

---
title: Solucao de Problemas
sidebar_position: 1
---

# Solucao de Problemas - Problemas Comuns e Solucoes

Este guia ajuda a diagnosticar e resolver problemas comuns ao usar o Tucano CVM.

## Problemas de Instalação

### Docker Compose não inicia

**Sintoma:**
```bash
docker compose up --build
# Erro: "Cannot connect to the Docker daemon"
```

**Solução:**
1. Verifique se o Docker está rodando:
   ```bash
   docker ps
   ```
2. Inicie o Docker Desktop (macOS/Windows) ou o serviço Docker (Linux):
   ```bash
   sudo systemctl start docker
   ```

### Migrações falham

**Sintoma:**
```bash
docker compose run --rm cvm_api alembic upgrade head
# Erro: "relation already exists"
```

**Solução:**
1. Limpe o banco de dados local:
   ```bash
   ./scripts/purge-local-db.sh --yes
   ```
2. Reaplique as migrações:
   ```bash
   docker compose run --rm cvm_api alembic upgrade head
   ```

### Variáveis de ambiente não carregadas

**Sintoma:**
```bash
# Erro: "DATABASE_URL is not set"
```

**Solução:**
1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```
2. Edite o `.env` com suas configurações
3. Reinicie os containers:
   ```bash
   docker compose down
   docker compose up --build
   ```

## Problemas de Autenticação

### Token expira rapidamente

**Sintoma:**
```bash
# Erro 401 após alguns minutos de uso
```

**Solução:**
1. Aumente o TTL do token no `.env`:
   ```bash
   ACCESS_TOKEN_TTL_MINUTES=480  # 8 horas (padrão)
   ```
2. Implemente renovacao automatica no cliente:

```python
import httpx


def refresh_token(base_url: str, credentials: dict[str, str]) -> str:
    response = httpx.post(f"{base_url}/auth/login", json=credentials, timeout=30.0)
    response.raise_for_status()
    return response.json()["access_token"]
```

### Usuário não pode criar outros usuários

**Sintoma:**
```bash
# Erro 403: "Permissao administrativa requerida"
```

**Solução:**
1. Verifique se o usuário tem `is_admin=true`:
   ```bash
   curl -H "Authorization: Bearer <token>" http://localhost:8007/auth/me
   ```
2. Se necessário, atualize o usuário:
   ```bash
   curl -X PATCH http://localhost:8007/usuarios/{id} \
     -H "Authorization: Bearer <admin-token>" \
     -d '{"is_admin": true}'
   ```

## Problemas de Consulta

### Companhia não encontrada

**Sintoma:**
```bash
# Erro 404: "Companhia nao encontrada"
```

**Solução:**
1. Verifique se o cadastro foi sincronizado:
   ```bash
   curl http://localhost:8007/ingestion/sincronizacoes?tipo_execucao=arquivo_simples
   ```
2. Dispare sincronização do cadastro:
   ```bash
   curl -X POST http://localhost:8007/ingestion/sincronizacoes/cadastro \
     -H "Authorization: Bearer <token>"
   ```
3. Aguarde a conclusão e tente novamente

### Dados financeiros vazios

**Sintoma:**
```bash
GET /dfp/documentos?codigo_cvm=25224
# Retorna {"dados": [], "paginacao": {...}}
```

**Solução:**
1. Verifique se os dados foram ingeridos:
   ```bash
   curl http://localhost:8007/ingestion/sincronizacoes?tipo_fonte=dfp
   ```
2. Dispare sincronização:
   ```bash
   curl -X POST http://localhost:8007/ingestion/sincronizacoes/dfp/2025 \
     -H "Authorization: Bearer <token>"
   ```
3. Monitore o progresso:
   ```bash
   curl http://localhost:8007/ingestion/dashboard
   ```

### Valores monetários incorretos

**Sintoma:**
```json
{
  "valor_conta": 740500.0,
  "valor_conta_reportado": 740500.0,
  "escala_moeda": "MIL"
}
```

**Explicação:**
- `valor_conta` já está ajustado pela escala (valor absoluto em reais)
- `valor_conta_reportado` é o valor bruto da CVM
- Use `valor_conta` para análises

**Fórmula:**
```
valor_conta = valor_conta_reportado × fator_escala_moeda
```

## Problemas de Ingestão

### Sincronização falha

**Sintoma:**
```bash
# Status: "falha" ou "falha_qualidade"
```

**Solução:**
1. Verifique os detalhes da execução:
   ```bash
   curl http://localhost:8007/ingestion/sincronizacoes/{id_execucao}
   ```
2. Verifique a mensagem de erro:
   ```json
   {
     "mensagem_erro": "Connection timeout",
     "status": "falha"
   }
   ```
3. Para erros de rede, tente novamente:
   ```bash
   curl -X POST http://localhost:8007/ingestion/sincronizacoes/dfp/2025 \
     -H "Authorization: Bearer <token>"
   ```

### Muitos itens em quarentena

**Sintoma:**
```bash
GET /ingestion/quarentena/resumo
# {"total": 500, ...}
```

**Solução:**
1. Identifique o motivo principal:
   ```bash
   curl http://localhost:8007/ingestion/quarentena/resumo
   ```
2. Se for `companhia_nao_encontrada`:
   ```bash
   # Sincronizar cadastro
   POST /ingestion/sincronizacoes/cadastro
   
   # Reconstruir grafo de identidade
   POST /ingestion/identity/rebuild
   
   # Replay da quarentena
   POST /ingestion/replay/quarentena
   {
     "reason_code": "companhia_nao_encontrada"
   }
   ```

### Execução presa em "aguardando_ingestao"

**Sintoma:**
```bash
# Status: "aguardando_ingestao" por muito tempo
```

**Solução:**
1. Dispare a Fase 2 manualmente:
   ```bash
   curl -X POST http://localhost:8007/ingestion/sincronizacoes/{id_execucao}/ingerir \
     -H "Authorization: Bearer <token>"
   ```
2. Verifique se os workers Celery estão rodando:
   ```bash
   docker compose ps cvm_worker
   ```
3. Reinicie os workers se necessário:
   ```bash
   docker compose restart cvm_worker
   ```

## Problemas de Performance

### Consultas lentas

**Sintoma:**
```bash
# Consultas demoram mais de 10 segundos
```

**Solução:**
1. Use filtros específicos:
   ```bash
   # Ruim: sem filtros
   GET /dfp/documentos
   
   # Bom: com filtros
   GET /dfp/documentos?codigo_cvm=25224&ano_inicio=2024
   ```
2. Limite o tamanho da página:
   ```bash
   GET /companhias?tamanho_pagina=100  # máximo 500
   ```
3. Use paginacao para iterar:

```python
import httpx


def iterar_todos(base_url: str, endpoint: str, token: str):
    pagina = 1
    while True:
        response = httpx.get(
            f"{base_url}{endpoint}",
            params={"pagina": pagina, "tamanho_pagina": 500},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        yield from data["dados"]
        if pagina * 500 >= data["paginacao"]["total"]:
            break
        pagina += 1
```

### Exportação em lote lenta

**Sintoma:**
```bash
# Exportação de 100.000 registros demora muito
```

**Solução:**
1. Use filtros para reduzir o volume:
   ```bash
   GET /exportacoes/dfp/bpa_con?codigo_cvm=25224&ano_inicio=2024
   ```
2. Prefira CSV para grandes volumes:
   ```bash
   GET /exportacoes/dfp/bpa_con?formato=csv
   ```
3. Aumente o timeout do cliente:

```python
import httpx

response = httpx.get(url, timeout=300.0)
response.raise_for_status()
```

## Problemas de Workers Celery

### Worker não processa tarefas

**Sintoma:**
```bash
# Tarefas ficam em "agendada" mas não executam
```

**Solução:**
1. Verifique se o Redis está rodando:
   ```bash
   docker compose ps cvm_redis
   ```
2. Verifique os logs do worker:
   ```bash
   docker compose logs cvm_worker
   ```
3. Reinicie o worker:
   ```bash
   docker compose restart cvm_worker
   ```

### Worker consome muita memória

**Sintoma:**
```bash
# Worker reinicia frequentemente
```

**Solução:**
1. Aumente o limite de memória no `.env`:
   ```bash
   CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB=2000000  # 2GB
   ```
2. Reduza o número de workers:
   ```bash
   # docker-compose.workers.yml
   cvm_worker:
     deploy:
       replicas: 2  # em vez de 4
   ```

## Problemas de Banco de Dados

### Conexão com PostgreSQL falha

**Sintoma:**
```bash
# Erro: "could not connect to server"
```

**Solução:**
1. Verifique se o PostgreSQL está rodando:
   ```bash
   docker compose ps postgres
   ```
2. Verifique a URL de conexão:
   ```bash
   echo $DATABASE_URL
   # postgresql://user:pass@postgres:5432/tucano_cvm
   ```
3. Reinicie o PostgreSQL:
   ```bash
   docker compose restart postgres
   ```

### Migrações conflitantes

**Sintoma:**
```bash
# Erro: "Migration already applied"
```

**Solução:**
1. Verifique o status das migrações:
   ```bash
   docker compose run --rm cvm_api alembic current
   ```
2. Reverta a última migração:
   ```bash
   docker compose run --rm cvm_api alembic downgrade -1
   ```
3. Reaplique:
   ```bash
   docker compose run --rm cvm_api alembic upgrade head
   ```

## Problemas de Dados

### Dados desatualizados

**Sintoma:**
```bash
# Dados com mais de 24 horas
```

**Solução:**
1. Verifique a última sincronização:
   ```bash
   curl http://localhost:8007/ingestion/dashboard
   ```
2. Dispare sincronização manual:
   ```bash
   curl -X POST http://localhost:8007/ingestion/sincronizacoes/tudo/2025 \
     -H "Authorization: Bearer <token>"
   ```
3. Verifique o Celery Beat:
   ```bash
   docker compose logs cvm_scheduler
   ```

### Dados inconsistentes entre fontes

**Sintoma:**
```bash
# DFP e FRE mostram valores diferentes
```

**Explicação:**
- DFP e FRE são documentos independentes
- Podem ter datas de referência diferentes
- Reapresentações podem ocorrer em momentos diferentes

**Solução:**
1. Verifique as datas de referência:
   ```bash
   GET /dfp/documentos?codigo_cvm=25224&ordenar_por=-data_referencia
   GET /fre/documentos?codigo_cvm=25224&ordenar_por=-data_referencia
   ```
2. Use a versão mais recente:
   ```bash
   GET /dfp/documentos?codigo_cvm=25224&versao=3
   ```

## Logs e Debugging

### Como acessar logs

```bash
# Logs da API
docker compose logs -f cvm_api

# Logs dos workers
docker compose logs -f cvm_worker

# Logs do scheduler
docker compose logs -f cvm_scheduler

# Logs do PostgreSQL
docker compose logs -f postgres

# Logs do Redis
docker compose logs -f cvm_redis
```

### Como habilitar debug

No `.env`:
```bash
LOG_LEVEL=DEBUG
```

Reinicie os serviços:
```bash
docker compose restart
```

### Como verificar saúde do sistema

```bash
# Healthcheck básico
curl http://localhost:8007/health

# Dashboard de execuções
curl -H "Authorization: Bearer <token>" \
  http://localhost:8007/ingestion/dashboard

# Status dos containers
docker compose ps
```

## Recursos Adicionais

- **[Glossário](./glossary.md)** - Termos técnicos
- **[Changelog](./changelog.md)** - Histórico de mudanças
- **OpenAPI da instancia** - disponivel em `/openapi.json` quando a API estiver em execucao

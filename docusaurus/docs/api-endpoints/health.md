---
title: Verificacao de Saude
sidebar_position: 3
---

# Verificacao de Saude

## Visão Geral

Endpoint público para verificação de disponibilidade da API. **Não requer autenticação**.

## Endpoint

| Método | Rota | Autenticação | Descrição |
|--------|------|--------------|-----------|
| `GET` | `/health` | **Não** | Verifica disponibilidade básica do serviço |

---

## `GET /health`

Retorna o status de saúde da API. Ideal para:

- **Liveness probes** (Kubernetes, Docker, load balancers)
- **Readiness probes** (verificar se a API está pronta para receber tráfego)
- **Monitoramento externo** (UptimeRobot, Datadog, etc.)
- **Scripts de verificação** antes de operações críticas

### Exemplo

```bash
curl -X GET "http://localhost:8007/health"
```

### Resposta 200

```json
{
  "status": "ok"
}
```

> **Nota:** A implementacao atual retorna `{"status": "ok"}`. O importante e que o endpoint responda com `200 OK` quando a API estiver operacional.

---

## Casos de Uso

### Kubernetes Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8007
  initialDelaySeconds: 10
  periodSeconds: 30
```

### Kubernetes Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8007
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Healthcheck no Docker Compose

```yaml
services:
  cvm_api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8007/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Script de Verificação (Bash)

```bash
#!/bin/bash
if curl -sf http://localhost:8007/health > /dev/null; then
  echo "API está saudável"
else
  echo "API indisponível"
  exit 1
fi
```

### Script de Verificação (Python)

```python
import httpx

def check_health(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/health", timeout=5.0)
        return response.status_code == 200
    except httpx.RequestError:
        return False

if check_health("http://localhost:8007"):
    print("API disponível")
else:
    print("API indisponível")
```

---

## Notas Importantes

- **Sem autenticação**: o `/health` é intencionalmente público para permitir probes de infraestrutura
- **Sem dependências críticas**: o endpoint verifica apenas se o servidor HTTP está respondendo
- **Não expõe dados sensíveis**: resposta mínima, sem informações internas
- **Idempotente**: pode ser chamado quantas vezes forem necessárias sem efeito colateral

## Quando NÃO usar

- ❌ Para verificar saúde do banco de dados (use métricas específicas)
- ❌ Para verificar saúde dos workers Celery (use `/ingestion/dashboard`)
- ❌ Para monitoramento de qualidade de dados (use endpoints de ingestão)

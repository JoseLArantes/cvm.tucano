---
title: Análise Pública de Companhias Selecionadas
sidebar_position: 8.5
---

# Análise Pública de Companhias Selecionadas

Esta seção documenta a superfície pública e isolada de dados analíticos. 

Para cenários onde dados de companhias específicas precisam ser expostos em portais abertos, sites institucionais ou sem necessidade de autenticação (Token Bearer), a plataforma Tucano CVM disponibiliza uma rota alternativa e cacheada no Redis sob o prefixo `/public/analise`.

---

## Características Principais

1. **Sem Autenticação**: Os endpoints não exigem cabeçalho `Authorization` ou Token Bearer.
2. **Camada de Caching (Redis)**: Para evitar sobrecarregar o banco de dados PostgreSQL com requisições públicas recorrentes, todas as respostas são armazenadas em cache no Redis.
   * **Cache Read-Through**: O primeiro acesso (cache miss) busca do banco de dados, serializa e guarda no Redis. Chamadas subsequentes (cache hit) leem a string serializada diretamente da memória do Redis.
   * **TTL Parametrizável**: O tempo de vida (TTL) do cache padrão é de 24 horas (`86400` segundos), configurável pela variável de ambiente `PUBLIC_CACHE_TTL_SECONDS`.
3. **Lista de Permissão (Allowlist)**: Apenas as companhias declaradas explicitamente na variável de ambiente `PUBLIC_COMPANIES_CVM` (ex: `PUBLIC_COMPANIES_CVM=12345,67890`) podem ser acessadas publicamente.
   * Se o `codigo_cvm` solicitado estiver na lista, a requisição é processada.
   * Se não estiver na lista, a resposta é imediata com status `403 Forbidden`.

---

## Tabela de Endpoints Públicos

Todas as rotas públicas realizam exatamente a mesma lógica de negócio e aceitam os mesmos parâmetros de consulta das suas contrapartes autenticadas da área `/analise`, retornando as mesmas estruturas de dados (Pydantic models).

| Método | Rota Pública | Descrição |
| :--- | :--- | :--- |
| `GET` | `/public/analise/companhias/{codigo_cvm}` | Manifesto analítico público (contexto, períodos e qualidade) |
| `GET` | `/public/analise/companhias/{codigo_cvm}/coverage` | Matriz de cobertura (dado bruto x fatos) pública |
| `GET` | `/public/analise/companhias/{codigo_cvm}/series` | Séries temporais analíticas normalizadas públicas |
| `GET` | `/public/analise/companhias/{codigo_cvm}/series/diagnostico` | Diagnóstico completo de lacunas públicas nas séries |
| `GET` | `/public/analise/companhias/{codigo_cvm}/comparacoes` | Comparações YoY/QoQ/CAGR prontas públicas |
| `GET` | `/public/analise/companhias/{codigo_cvm}/qualidade` | Verificações de qualidade de dados públicas |
| `GET` | `/public/analise/companhias/{codigo_cvm}/sinais` | Sinais e limites determinísticos públicos com evidências |
| `GET` | `/public/analise/companhias/{codigo_cvm}/eventos` | Timeline analítica pública |
| `GET` | `/public/analise/companhias/{codigo_cvm}/governanca` | Governança analítica e temporal pública |
| `GET` | `/public/analise/companhias/{codigo_cvm}/pessoas` | Pessoas e remuneração temporal pública |
| `GET` | `/public/analise/companhias/{codigo_cvm}/brief` | Brief analítico consolidado e compacto público |
| `GET` | `/public/analise/companhias/{codigo_cvm}/restatements` | Histórico de reapresentações e alterações públicas |

---

## Exemplos de Uso

### 1. Chamada de Séries Temporais (Miss / Hit)
```bash
curl -X GET "http://localhost:8007/public/analise/companhias/12345/series?periodicidade=annual&base_periodo=fy"
```

**Comportamento do Servidor**:
* O backend valida se `12345` está contido na lista `PUBLIC_COMPANIES_CVM`.
* Caso esteja, calcula o hash dos parâmetros query e busca pela chave no Redis.
* Se for a primeira chamada, lê do Postgres, computa e serializa a resposta em JSON. A seguir, salva essa string no Redis sob a chave `public:analise:series:12345:xxxxxxxxx` com o TTL configurado.
* Retorna o JSON ao cliente.

### 2. Chamada Negada (Companhia Não Autorizada)
```bash
curl -i -X GET "http://localhost:8007/public/analise/companhias/99999/series"
```
**Resposta do Servidor**:
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "detail": "Acesso nao autorizado para esta companhia."
}
```

---
title: Autenticacao
sidebar_position: 1
---

# Autenticacao

## Visão Geral

A API utiliza autenticação baseada em **tokens Bearer (JWT)** com prefixo customizado `tucano.v1.`. Todos os endpoints protegidos exigem o header `Authorization: Bearer <access_token>`.

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/auth/login` | Realizar login e obter token |
| `GET` | `/auth/me` | Obter dados do usuário autenticado |

---

## `POST /auth/login`

Autentica um usuário cadastrado e emite um token temporário.

### Fluxo Esperado

1. Um administrador cria o usuário via `POST /usuarios` usando o token de sistema ou um usuário com `is_admin=true`
2. A API valida: usuário ativo, hash da senha e credenciais informadas
3. A API retorna `access_token`, `token_type` e `expires_in`

### Regras de Autenticação

- `username` é **normalizado para minúsculas** antes da busca (trim + lowercase)
- O usuário precisa existir e estar com `ativo=true`
- O token expira conforme `ACCESS_TOKEN_TTL_MINUTES` (padrão: **480 minutos = 8 horas**)
- Se o usuário for desativado **depois** do login, tokens já emitidos deixam de ser aceitos

### Request Body

**Schema:** `LoginRequisicao`

```json
{
  "username": "admin",
  "password": "senha-admin-segura"
}
```

| Campo | Tipo | Obrigatório | Restrições | Descrição |
|-------|------|-------------|------------|-----------|
| `username` | string | Sim | 3-150 caracteres | Identificador do usuário. Espaços nas extremidades são removidos; comparação em minúsculas. |
| `password` | string | Sim | 8-256 caracteres | Senha atual. Nunca aparece em respostas da API. |

### Response 200

**Schema:** `LoginResposta`

```json
{
  "access_token": "tucano.v1.eyJleHAiOjE3ODA1MjIzNTksInN1YiI6Ii4uLiJ9.assinatura",
  "token_type": "bearer",
  "expires_in": 28800
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `access_token` | string | Token assinado. Envie no header `Authorization: Bearer <token>` |
| `token_type` | string | Sempre `"bearer"` |
| `expires_in` | integer | Validade em segundos (derivado de `ACCESS_TOKEN_TTL_MINUTES`) |

### Códigos de Erro

| Status | Descrição | Exemplo |
|--------|-----------|---------|
| `401` | Credenciais inválidas, usuário inexistente ou inativo | `{"detail": "Usuario ou senha invalidos."}` |
| `422` | Payload inválido ou campos obrigatórios ausentes | `{"detail": [{"type": "missing", "loc": ["body", "password"], ...}]}` |

### Exemplo cURL

```bash
curl -X POST "http://localhost:8007/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "senha-admin-segura"
  }'
```

### Exemplo Python (httpx)

```python
import httpx

response = httpx.post(
    "http://localhost:8007/auth/login",
    json={"username": "admin", "password": "senha-admin-segura"}
)

if response.status_code == 200:
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
```

### Exemplo JavaScript (fetch)

```javascript
const response = await fetch('http://localhost:8007/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'senha-admin-segura'
  })
});

const { access_token } = await response.json();
```

---

## `GET /auth/me`

Retorna os dados do usuário autenticado pelo token bearer.

### Headers Obrigatórios

```
Authorization: Bearer <access_token>
```

### Response 200

**Schema:** `UsuarioResposta`

```json
{
  "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
  "username": "admin",
  "nome": "Administrador",
  "is_admin": true,
  "ativo": true,
  "criado_em": "2026-01-15T10:30:00Z",
  "alterado_em": "2026-01-15T10:30:00Z"
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Identificador interno do usuário |
| `username` | string | Identificador usado no login |
| `nome` | string \| null | Nome de exibição |
| `is_admin` | boolean | Indica se pode administrar outros usuários |
| `ativo` | boolean | Indica se login e tokens são aceitos |
| `criado_em` | datetime (ISO 8601) | Timestamp de criação |
| `alterado_em` | datetime (ISO 8601) | Timestamp da última alteração |

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `401` | Token ausente, inválido ou expirado |

---

## Fluxo de Bootstrap (Primeiro Usuário)

Como a API exige autenticação para quase tudo, o **primeiro usuário administrativo** deve ser criado usando o **token de sistema** (`TUCANO_CVM_TOKEN`):

```bash
curl -X POST "http://localhost:8007/usuarios" \
  -H "Authorization: Bearer $TUCANO_CVM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "senha-admin-segura",
    "nome": "Administrador Inicial",
    "is_admin": true,
    "ativo": true
  }'
```

Após isso, o administrador pode criar outros usuários via `POST /usuarios`.

---

## Gerenciamento de Tokens

### Renovação

A API **não possui endpoint de refresh token**. Quando o token expira, o cliente deve:

1. Detectar `401 Unauthorized`
2. Solicitar credenciais novamente (se necessário)
3. Chamar `POST /auth/login` para obter novo token

### TTL Padrão

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `ACCESS_TOKEN_TTL_MINUTES` | `480` | Tempo de vida do token em minutos |

### Boas Práticas

- **Armazene tokens com segurança**: não exponha em logs, código-fonte ou URLs
- **Use HTTPS em produção**: tokens trafegam em header e precisam de canal seguro
- **Implemente cache de token**: evite login a cada requisição
- **Trate expiração gracefulmente**: redirecione para login quando receber `401`
- **Revogação**: desativar o usuário (`ativo=false`) invalida imediatamente todos os tokens emitidos

---

## Notas para Usuários

### Para Analistas Financeiros

Use o token para consultar dados financeiros (DFP, ITR, FRE). O token é válido por 8 horas por padrão, suficiente para sessões de análise.

### Para Auditores

O endpoint `/auth/me` permite confirmar qual identidade está autenticada antes de operações críticas de consulta.

### Para Operadores de Backoffice

Implemente renovação automática de token em scripts de sincronização para evitar falhas em execuções longas.

### Para Compliance

Tokens são rastreáveis: cada token está vinculado a um `usuario_id`. Logs de acesso podem ser correlacionados com identidades específicas.

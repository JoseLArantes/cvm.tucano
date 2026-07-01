---
title: Autenticação
sidebar_position: 2
---

# Autenticação

O Tucano CVM usa autenticação baseada em tokens Bearer (JWT). A maioria dos endpoints requer autenticação.

## Endpoints Públicos

Apenas o endpoint `/health` é público e não requer autenticação:

```bash
curl http://localhost:8007/health
```

## Criando o Primeiro Usuário

### Método 1: Usando Token de Sistema

O token de sistema (`TUCANO_CVM_TOKEN`) pode ser usado para criar o primeiro usuário administrativo:

```bash
curl -X POST "http://localhost:8007/usuarios" \
  -H "Authorization: Bearer seu-token-de-sistema" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "senha-segura-aqui",
    "nome": "Administrador",
    "is_admin": true,
    "ativo": true
  }'
```

### Método 2: Usando Usuário Admin Existente

Se já existe um usuário administrativo, ele pode criar outros usuários:

```bash
curl -X POST "http://localhost:8007/usuarios" \
  -H "Authorization: Bearer token-do-admin" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analista",
    "password": "senha-segura",
    "nome": "Analista Financeiro",
    "is_admin": false,
    "ativo": true
  }'
```

Para delegar apenas a operação de recuperação da materialização analítica, crie ou atualize usuários com `pode_operar_materializacao=true` e mantenha `is_admin=false` quando não houver necessidade de administração ampla.

## Realizando Login

Para obter um token de acesso:

```bash
curl -X POST "http://localhost:8007/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "senha-segura-aqui"
  }'
```

**Resposta:**

```json
{
  "access_token": "tucano.v1.eyJleHAiOjE3ODA1MjIzNTksInN1YiI6Ii4uLiJ9.assinatura",
  "token_type": "bearer",
  "expires_in": 28800
}
```

### Campos da Resposta

| Campo | Descrição |
|-------|-----------|
| `access_token` | Token JWT para autenticação |
| `token_type` | Tipo do token (sempre "bearer") |
| `expires_in` | Tempo de vida em segundos (padrão: 28800 = 8 horas) |

## Usando o Token

Inclua o token no header `Authorization` de todas as requisições:

```bash
curl -X GET "http://localhost:8007/companhias" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Exemplo em Python

```python
import httpx

# Realizar login
login_response = httpx.post(
    "http://localhost:8007/auth/login",
    json={
        "username": "admin",
        "password": "senha-segura-aqui"
    }
)
token = login_response.json()["access_token"]

# Usar o token
headers = {"Authorization": f"Bearer {token}"}
response = httpx.get(
    "http://localhost:8007/companhias",
    headers=headers
)
```

### Exemplo em JavaScript

```javascript
// Realizar login
const loginResponse = await fetch('http://localhost:8007/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'senha-segura-aqui'
  })
});
const { access_token } = await loginResponse.json();

// Usar o token
const response = await fetch('http://localhost:8007/companhias', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
const data = await response.json();
```

## Verificando Usuário Autenticado

Para obter informações do usuário autenticado:

```bash
curl -X GET "http://localhost:8007/auth/me" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta:**

```json
{
  "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
  "username": "admin",
  "nome": "Administrador",
  "is_admin": true,
  "pode_operar_materializacao": true,
  "ativo": true,
  "criado_em": "2026-01-15T10:30:00Z",
  "alterado_em": "2026-01-15T10:30:00Z"
}
```

## Gerenciamento de Usuários

### Listar Usuários

```bash
curl -X GET "http://localhost:8007/usuarios" \
  -H "Authorization: Bearer token-admin"
```

**Parâmetros de Query:**

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `ativo` | boolean | Filtrar por status ativo/inativo |
| `pagina` | integer | Número da página (padrão: 1) |
| `tamanho_pagina` | integer | Itens por página (padrão: 100, máx: 500) |

### Obter Usuário por ID

```bash
curl -X GET "http://localhost:8007/usuarios/{usuario_id}" \
  -H "Authorization: Bearer token-admin"
```

### Atualizar Usuário

```bash
curl -X PATCH "http://localhost:8007/usuarios/{usuario_id}" \
  -H "Authorization: Bearer token-admin" \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Novo Nome",
    "is_admin": false,
    "ativo": true
  }'
```

### Excluir Usuário

```bash
curl -X DELETE "http://localhost:8007/usuarios/{usuario_id}" \
  -H "Authorization: Bearer token-admin"
```

## Regras de Autenticação

1. **Username Normalizado**: O username é normalizado para minúsculas antes da busca
2. **Usuário Ativo**: O usuário precisa existir e estar com `ativo=true`
3. **Token Expira**: Tokens expiram conforme `ACCESS_TOKEN_TTL_MINUTES` (padrão: 480 minutos)
4. **Usuário Desativado**: Se o usuário for desativado depois do login, tokens já emitidos deixam de ser aceitos
5. **Capacidades Persistidas**: O token expõe as capacidades do usuário, incluindo `is_admin` e `pode_operar_materializacao`

## Códigos de Erro Comuns

| Código | Descrição |
|--------|-----------|
| `401` | Credenciais inválidas, usuário inexistente ou usuário inativo |
| `403` | Permissão administrativa requerida |
| `422` | Payload inválido ou campos obrigatórios ausentes |

### Exemplo de Erro 401

```json
{
  "detail": "Usuario ou senha invalidos."
}
```

### Exemplo de Erro 422

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "password"],
      "msg": "Field required",
      "input": {"username": "admin"}
    }
  ]
}
```

## Melhores Práticas

1. **Armazene Tokens com Segurança**: Não exponha tokens em logs ou código-fonte
2. **Renove Tokens**: Tokens expiram; implemente renovação automática
3. **Use HTTPS**: Em produção, sempre use HTTPS para proteger tokens em trânsito
4. **Limite Permissões**: Use `is_admin=false` para usuários que não precisam administrar
5. **Delegue Operação sem Admin**: Use `pode_operar_materializacao=true` para recovery operacional de materialização
6. **Monitore Uso**: Acompanhe logs de autenticação para detectar uso indevido

## Próximos Passos

Após configurar a autenticação, consulte:

1. [Inicio Rapido](./quickstart.md) - Primeiras consultas
2. [API Endpoints](../api-endpoints/auth.md) - Referência completa de autenticação

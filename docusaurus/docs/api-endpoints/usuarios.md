---
title: Gerenciamento de Usuários
sidebar_position: 2
---

# Gerenciamento de Usuários

## Visão Geral

Endpoints para CRUD de usuários da API. **Todas as operações exigem permissão administrativa** (token de sistema ou usuário com `is_admin=true`).

## Endpoints

| Método | Rota | Descrição | Permissão |
|--------|------|-----------|-----------|
| `GET` | `/usuarios` | Listar usuários | Admin |
| `POST` | `/usuarios` | Criar usuário | Admin |
| `GET` | `/usuarios/{usuario_id}` | Obter usuário por ID | Admin |
| `PATCH` | `/usuarios/{usuario_id}` | Atualizar usuário | Admin |
| `DELETE` | `/usuarios/{usuario_id}` | Excluir usuário | Admin |

---

## `GET /usuarios`

Lista usuários cadastrados com paginação.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `ativo` | boolean | - | Filtra usuários ativos ou inativos |
| `pagina` | integer | `1` | Número da página (inicia em 1) |
| `tamanho_pagina` | integer | `100` | Itens por página (máx: 500) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/usuarios?ativo=true&pagina=1&tamanho_pagina=50" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaUsuariosResposta`

```json
{
  "dados": [
    {
      "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
      "username": "admin",
      "nome": "Administrador",
      "is_admin": true,
      "ativo": true,
      "criado_em": "2026-01-15T10:30:00Z",
      "alterado_em": "2026-01-15T10:30:00Z"
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 50,
    "total": 1
  }
}
```

---

## `POST /usuarios`

Cria um novo usuário para login na API.

### Request Body

**Schema:** `UsuarioCriacao`

```json
{
  "username": "analista",
  "password": "senha-segura-123",
  "nome": "Analista Financeiro",
  "is_admin": false,
  "ativo": true
}
```

| Campo | Tipo | Obrigatório | Restrições | Descrição |
|-------|------|-------------|------------|-----------|
| `username` | string | Sim | 3-150 chars, regex `^[a-zA-Z0-9_.@-]+$` | Identificador único usado no login |
| `password` | string | Sim | 8-256 caracteres | Senha inicial |
| `nome` | string | Não | máx 255 chars | Nome de exibição |
| `is_admin` | boolean | Não | padrão `false` | Permite administrar usuários |
| `ativo` | boolean | Não | padrão `true` | Permite login e uso de tokens |

### Response 201

**Schema:** `UsuarioResposta`

```json
{
  "id": "a1b2c3d4-...",
  "username": "analista",
  "nome": "Analista Financeiro",
  "is_admin": false,
  "ativo": true,
  "criado_em": "2026-06-17T10:00:00Z",
  "alterado_em": "2026-06-17T10:00:00Z"
}
```

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `401` | Token ausente ou inválido |
| `403` | Permissão administrativa requerida |
| `409` | Username já cadastrado |
| `422` | Validação de payload falhou |

### Exemplo cURL

```bash
curl -X POST "http://localhost:8007/usuarios" \
  -H "Authorization: Bearer <token-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analista",
    "password": "senha-segura-123",
    "nome": "Analista Financeiro",
    "is_admin": false,
    "ativo": true
  }'
```

---

## `GET /usuarios/{usuario_id}`

Retorna um usuário específico por ID.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `usuario_id` | UUID | ID do usuário |

### Exemplo

```bash
curl -X GET "http://localhost:8007/usuarios/f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `UsuarioResposta` (mesmo formato do `POST`)

---

## `PATCH /usuarios/{usuario_id}`

Atualiza dados, senha, status e perfil administrativo de um usuário.

### Path Parameters

| Parâmetro | Tipo |
|-----------|------|
| `usuario_id` | UUID |

### Request Body

**Schema:** `UsuarioAtualizacao` (todos os campos são opcionais)

```json
{
  "nome": "Novo Nome",
  "is_admin": false,
  "ativo": true,
  "password": "nova-senha-segura",
  "username": "novo_username"
}
```

| Campo | Tipo | Restrições | Descrição |
|-------|------|------------|-----------|
| `username` | string | 3-150 chars, regex `^[a-zA-Z0-9_.@-]+$` | Novo identificador de login |
| `password` | string | 8-256 caracteres | Nova senha |
| `nome` | string | máx 255 chars | Novo nome de exibição |
| `is_admin` | boolean | - | Novo status administrativo |
| `ativo` | boolean | - | Novo status de ativação |

### Response 200

**Schema:** `UsuarioResposta`

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `401` | Token ausente ou inválido |
| `403` | Permissão administrativa requerida |
| `404` | Usuário não encontrado |
| `409` | Username já cadastrado |

### Exemplo: Desativar Usuário

```bash
curl -X PATCH "http://localhost:8007/usuarios/f4f6a9d8-..." \
  -H "Authorization: Bearer <token-admin>" \
  -H "Content-Type: application/json" \
  -d '{"ativo": false}'
```

> **Importante:** Desativar um usuário invalida **imediatamente** todos os tokens emitidos para ele.

---

## `DELETE /usuarios/{usuario_id}`

Remove um usuário cadastrado.

### Path Parameters

| Parâmetro | Tipo |
|-----------|------|
| `usuario_id` | UUID |

### Response 204

Sem conteúdo (sucesso).

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `401` | Token ausente ou inválido |
| `403` | Permissão administrativa requerida |
| `404` | Usuário não encontrado |

### Exemplo

```bash
curl -X DELETE "http://localhost:8007/usuarios/f4f6a9d8-..." \
  -H "Authorization: Bearer <token-admin>"
```

---

## Estratégias de Uso por Perfil

### Para Administradores de Sistema

- Crie usuários com `is_admin=false` para operadores e analistas
- Use `ativo=false` para suspender acessos sem excluir o histórico
- Mantenha um usuário administrativo de backup

### Para Gestores de Compliance

- Monitore criação e desativação de usuários
- Prefira desativar em vez de excluir para preservar audit trail
- Revise periodicamente usuários com `is_admin=true`

### Para Operadores de Backoffice

- Crie usuários específicos para integrações (ex: `integration-etl`)
- Use senhas fortes e rotacione periodicamente
- Documente quais tokens estão em uso por sistema

---

## Segurança

### Recomendações

1. **Senhas fortes**: mínimo 8 caracteres, combine letras, números e símbolos
2. **Princípio do menor privilégio**: use `is_admin=false` sempre que possível
3. **Rotação de credenciais**: altere senhas periodicamente via `PATCH`
4. **Auditoria**: registre criação, alteração e desativação de usuários
5. **Backup**: mantenha pelo menos dois usuários administrativos ativos

### O que NÃO fazer

- ❌ Compartilhar tokens entre usuários
- ❌ Armazenar senhas em texto plano
- ❌ Excluir o último usuário administrativo
- ❌ Usar o token de sistema (`TUCANO_CVM_TOKEN`) em produção para operações rotineiras
---
title: Schemas de Autenticação
sidebar_position: 2
---

# Schemas de Autenticação

## `LoginRequisicao`

Request body para `POST /auth/login`.

### Schema

```python
class LoginRequisicao(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=150,
        description="Identificador do usuário. Espaços nas extremidades são removidos; comparação em minúsculas.",
        examples=["admin", "frontend"]
    )
    password: str = Field(
        min_length=8,
        max_length=256,
        description="Senha atual do usuário. Nunca aparece em respostas da API.",
        examples=["senha-admin-segura"]
    )
```

### Exemplo JSON

```json
{
  "username": "admin",
  "password": "senha-admin-segura"
}
```

### Validações

- `username`: mínimo 3 caracteres, máximo 150
- `password`: mínimo 8 caracteres, máximo 256
- `username` é normalizado para minúsculas antes da busca

---

## `LoginResposta`

Response para `POST /auth/login`.

### Schema

```python
class LoginResposta(BaseModel):
    access_token: str = Field(
        description="Token assinado emitido. Envie no header Authorization: Bearer <token>.",
        examples=["tucano.v1.eyJleHAiOjE3ODA1MjIzNTksInN1YiI6Ii4uLiJ9.assinatura"]
    )
    token_type: str = Field(
        description="Tipo do token. Sempre 'bearer'.",
        examples=["bearer"]
    )
    expires_in: int = Field(
        description="Tempo de validade em segundos. Derivado de ACCESS_TOKEN_TTL_MINUTES.",
        examples=[28800]
    )
```

### Exemplo JSON

```json
{
  "access_token": "tucano.v1.eyJleHAiOjE3ODA1MjIzNTksInN1YiI6Ii4uLiJ9.assinatura",
  "token_type": "bearer",
  "expires_in": 28800
}
```

### Campos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `access_token` | string | Token JWT com prefixo `tucano.v1.` |
| `token_type` | string | Sempre `"bearer"` |
| `expires_in` | integer | Validade em segundos (padrão: 28800 = 8h) |

---

## `UsuarioResposta`

Response para `GET /auth/me`, `GET /usuarios/{id}`, `POST /usuarios`, `PATCH /usuarios/{id}`.

### Schema

```python
class UsuarioResposta(BaseModel):
    id: UUID = Field(description="Identificador interno do usuário.")
    username: str = Field(description="Identificador usado no login.")
    nome: Optional[str] = Field(description="Nome de exibição.")
    is_admin: bool = Field(description="Indica se pode administrar usuários.")
    ativo: bool = Field(description="Indica se login e tokens são aceitos.")
    criado_em: datetime = Field(description="Timestamp de criação (UTC).")
    alterado_em: datetime = Field(description="Timestamp da última alteração (UTC).")
```

### Exemplo JSON

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

---

## `UsuarioCriacao`

Request body para `POST /usuarios`.

### Schema

```python
class UsuarioCriacao(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=150,
        pattern=r"^[a-zA-Z0-9_.@-]+$",
        description="Identificador único usado no login.",
        examples=["frontend"]
    )
    password: str = Field(
        min_length=8,
        max_length=256,
        description="Senha inicial do usuário."
    )
    nome: Optional[str] = Field(
        max_length=255,
        description="Nome de exibição do usuário."
    )
    is_admin: bool = Field(
        default=False,
        description="Permite administrar usuários."
    )
    ativo: bool = Field(
        default=True,
        description="Permite login e uso do token."
    )
```

### Exemplo JSON

```json
{
  "username": "analista",
  "password": "senha-segura-123",
  "nome": "Analista Financeiro",
  "is_admin": false,
  "ativo": true
}
```

### Validações

- `username`: regex `^[a-zA-Z0-9_.@-]+$`, 3-150 caracteres
- `password`: 8-256 caracteres
- `nome`: máximo 255 caracteres (opcional)

---

## `UsuarioAtualizacao`

Request body para `PATCH /usuarios/{id}`. Todos os campos são opcionais.

### Schema

```python
class UsuarioAtualizacao(BaseModel):
    username: Optional[str] = Field(
        min_length=3,
        max_length=150,
        pattern=r"^[a-zA-Z0-9_.@-]+$",
        description="Novo identificador de login."
    )
    password: Optional[str] = Field(
        min_length=8,
        max_length=256,
        description="Nova senha."
    )
    nome: Optional[str] = Field(
        max_length=255,
        description="Novo nome de exibição."
    )
    is_admin: Optional[bool] = Field(
        description="Novo status administrativo."
    )
    ativo: Optional[bool] = Field(
        description="Novo status de ativação."
    )
```

### Exemplo JSON

```json
{
  "nome": "Novo Nome",
  "is_admin": false,
  "ativo": true
}
```

---

## `ListaUsuariosResposta`

Response para `GET /usuarios`.

### Schema

```python
class ListaUsuariosResposta(BaseModel):
    dados: List[UsuarioResposta] = Field(description="Lista paginada de usuários.")
    paginacao: Paginacao = Field(description="Metadados de paginação.")
```

### Exemplo JSON

```json
{
  "dados": [
    {
      "id": "f4f6a9d8-...",
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
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

---

## Códigos de Erro

| Status | Descrição | Schema |
|--------|-----------|--------|
| `401` | Credenciais inválidas | `{"detail": "Usuario ou senha invalidos."}` |
| `403` | Permissão administrativa requerida | `{"detail": "Permissao administrativa requerida."}` |
| `404` | Usuário não encontrado | `{"detail": "Usuario nao encontrado."}` |
| `409` | Username já cadastrado | `{"detail": "Username ja cadastrado."}` |
| `422` | Validação falhou | `HTTPValidationError` |

---

## Exemplo Completo: Fluxo de Login

### 1. Criar Usuário (Admin)

```bash
POST /usuarios
Authorization: Bearer <token-sistema>
Content-Type: application/json

{
  "username": "analista",
  "password": "senha-segura-123",
  "nome": "Analista Financeiro",
  "is_admin": false,
  "ativo": true
}
```

### 2. Realizar Login

```bash
POST /auth/login
Content-Type: application/json

{
  "username": "analista",
  "password": "senha-segura-123"
}
```

**Response 200:**
```json
{
  "access_token": "tucano.v1.eyJ...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

### 3. Usar Token

```bash
GET /auth/me
Authorization: Bearer tucano.v1.eyJ...
```

**Response 200:**
```json
{
  "id": "...",
  "username": "analista",
  "nome": "Analista Financeiro",
  "is_admin": false,
  "ativo": true,
  "criado_em": "2026-06-17T10:00:00Z",
  "alterado_em": "2026-06-17T10:00:00Z"
}
```
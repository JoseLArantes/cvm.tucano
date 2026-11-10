"""add versioned sector dictionaries and company classifications

Revision ID: 20261109_001
Revises: 20261103_001
Create Date: 2026-11-09
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20261109_001"
down_revision: str | None = "20261103_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SPACES = re.compile(r"\s+")


def _key(label: str) -> str:
    compactado = _SPACES.sub(" ", unicodedata.normalize("NFC", label).strip())
    return unicodedata.normalize("NFC", compactado.lower())


def upgrade() -> None:
    op.create_table(
        "setor_taxonomias",
        sa.Column("codigo", sa.String(64), primary_key=True),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("versao_atual", sa.Integer()),
        sa.Column("checksum_atual", sa.String(64)),
        sa.Column("referencia_fonte_atual", sa.String(255)),
        sa.Column("publicada_em", sa.DateTime(timezone=True)),
        sa.Column("alterada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "setor_taxonomia_versoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("taxonomia", sa.String(64), sa.ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("checksum_fonte", sa.String(64)),
        sa.Column("checksum_semantico", sa.String(64), nullable=False),
        sa.Column("referencia_fonte", sa.String(255)),
        sa.Column("observada_em", sa.DateTime(timezone=True)),
        sa.Column("publicada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resumo", sa.JSON(), nullable=False),
        sa.UniqueConstraint("taxonomia", "versao", name="uq_setor_taxonomia_versao"),
    )
    op.create_index("ix_setor_taxonomia_versoes_taxonomia", "setor_taxonomia_versoes", ["taxonomia"])
    op.create_index("ix_setor_taxonomia_versoes_publicada", "setor_taxonomia_versoes", ["taxonomia", "publicada_em"])
    op.create_table(
        "setores",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("taxonomia", sa.String(64), sa.ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"), nullable=False),
        sa.Column("chave_normalizada", sa.String(255), nullable=False),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("nivel", sa.String(64), nullable=False),
        sa.Column("setor_pai_id", sa.Uuid(), sa.ForeignKey("setores.id", ondelete="RESTRICT")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("alterado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("taxonomia", "chave_normalizada", name="uq_setores_taxonomia_chave"),
    )
    op.create_index("ix_setores_taxonomia", "setores", ["taxonomia"])
    op.create_index("ix_setores_taxonomia_pai", "setores", ["taxonomia", "setor_pai_id"])
    op.create_table(
        "setor_aliases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("taxonomia", sa.String(64), nullable=False),
        sa.Column("setor_id", sa.Uuid(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chave_normalizada", sa.String(255), nullable=False),
        sa.Column("rotulo_origem", sa.String(255), nullable=False),
        sa.Column("evidencias", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("taxonomia", "chave_normalizada", name="uq_setor_alias_taxonomia_chave"),
    )
    op.create_index("ix_setor_aliases_taxonomia", "setor_aliases", ["taxonomia"])
    op.create_index("ix_setor_aliases_setor_id", "setor_aliases", ["setor_id"])
    op.create_table(
        "setor_classificacoes_companhia",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("companhia_id", sa.Uuid(), sa.ForeignKey("companhias.id", ondelete="CASCADE"), nullable=False),
        sa.Column("taxonomia", sa.String(64), sa.ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"), nullable=False),
        sa.Column("setor_id", sa.Uuid(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rotulo_origem", sa.String(255), nullable=False),
        sa.Column("fonte", sa.String(64), nullable=False),
        sa.Column("referencia_fonte", sa.String(255)),
        sa.Column("arquivo_origem", sa.String(255)),
        sa.Column("linha_origem", sa.Integer()),
        sa.Column("versao_inicio", sa.Integer(), nullable=False),
        sa.Column("versao_fim", sa.Integer()),
        sa.Column("inicio_vigencia", sa.DateTime(timezone=True)),
        sa.Column("fim_vigencia", sa.DateTime(timezone=True)),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_setor_classificacoes_companhia_id", "setor_classificacoes_companhia", ["companhia_id"])
    op.create_index(
        "ix_setor_classificacoes_taxonomia_setor_companhia_atual",
        "setor_classificacoes_companhia",
        ["taxonomia", "setor_id", "companhia_id"],
        sqlite_where=sa.text("versao_fim IS NULL"),
        postgresql_where=sa.text("versao_fim IS NULL"),
    )
    op.create_index(
        "ix_setor_classificacoes_companhia_taxonomia_atual",
        "setor_classificacoes_companhia",
        ["companhia_id", "taxonomia"],
        unique=True,
        sqlite_where=sa.text("versao_fim IS NULL"),
        postgresql_where=sa.text("versao_fim IS NULL"),
    )
    op.create_table(
        "setor_correspondencias",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("taxonomia_origem", sa.String(64), sa.ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"), nullable=False),
        sa.Column("setor_origem_id", sa.Uuid(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("taxonomia_destino", sa.String(64), sa.ForeignKey("setor_taxonomias.codigo", ondelete="RESTRICT"), nullable=False),
        sa.Column("setor_destino_id", sa.Uuid(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("versao_mapeamento", sa.Integer(), nullable=False),
        sa.Column("evidencias", sa.JSON(), nullable=False),
        sa.Column("justificativa", sa.Text()),
        sa.Column("revisado_por", sa.String(128)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "taxonomia_origem",
            "setor_origem_id",
            "taxonomia_destino",
            "setor_destino_id",
            "versao_mapeamento",
            name="uq_setor_correspondencia_versao",
        ),
    )
    op.create_index("ix_setor_correspondencias_origem", "setor_correspondencias", ["taxonomia_origem", "setor_origem_id"])
    op.create_index("ix_setor_correspondencias_destino", "setor_correspondencias", ["taxonomia_destino", "setor_destino_id"])
    op.create_table(
        "setor_taxonomia_mudancas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("publicacao_id", sa.Uuid(), sa.ForeignKey("setor_taxonomia_versoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("companhia_id", sa.Uuid(), sa.ForeignKey("companhias.id", ondelete="SET NULL")),
        sa.Column("setor_id", sa.Uuid(), sa.ForeignKey("setores.id", ondelete="SET NULL")),
        sa.Column("antes", sa.JSON()),
        sa.Column("depois", sa.JSON()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_setor_taxonomia_mudancas_publicacao_id", "setor_taxonomia_mudancas", ["publicacao_id"])
    op.create_index("ix_setor_taxonomia_mudancas_versao", "setor_taxonomia_mudancas", ["publicacao_id", "tipo"])
    op.create_index("ix_setor_taxonomia_mudancas_companhia", "setor_taxonomia_mudancas", ["companhia_id", "criado_em"])

    bind = op.get_bind()
    agora = datetime.now(UTC)
    bind.execute(
        sa.text(
            "INSERT INTO setor_taxonomias (codigo, nome, fonte, ativa) VALUES "
            "(:codigo, :nome, :fonte, :ativa)"
        ),
        [
            {"codigo": "cvm_cadastro", "nome": "Setor de atividade CVM", "fonte": "Cadastro de companhias da CVM", "ativa": True},
            {"codigo": "b3", "nome": "Classificação setorial B3", "fonte": "Fonte oficial autorizada pendente", "ativa": False},
        ],
    )
    companhias = bind.execute(
        sa.text("SELECT id, setor_atividade, arquivo_origem, linha_origem FROM companhias ORDER BY id")
    ).mappings().all()
    labels: dict[str, str] = {}
    for companhia in companhias:
        raw = (companhia["setor_atividade"] or "").strip()
        if raw:
            key = _key(raw)
            labels.setdefault(key, _SPACES.sub(" ", unicodedata.normalize("NFC", raw)))
    setores = {key: uuid.uuid4() for key in sorted(labels)}
    setor_rows = [
        {
            "id": setores[key],
            "taxonomia": "cvm_cadastro",
            "chave_normalizada": key,
            "nome": labels[key],
            "nivel": "setor",
            "ativo": True,
            "criado_em": agora,
            "alterado_em": agora,
        }
        for key in sorted(labels)
    ]
    if setor_rows:
        setores_table = sa.table(
            "setores",
            sa.column("id", sa.Uuid()),
            sa.column("taxonomia", sa.String(64)),
            sa.column("chave_normalizada", sa.String(255)),
            sa.column("nome", sa.String(255)),
            sa.column("nivel", sa.String(64)),
            sa.column("ativo", sa.Boolean()),
            sa.column("criado_em", sa.DateTime(timezone=True)),
            sa.column("alterado_em", sa.DateTime(timezone=True)),
        )
        bind.execute(sa.insert(setores_table), setor_rows)
    atribuicoes = []
    semantic_rows = []
    for companhia in companhias:
        companhia_id = uuid.UUID(str(companhia["id"]))
        raw = (companhia["setor_atividade"] or "").strip()
        sector_id = setores.get(_key(raw)) if raw else None
        semantic_rows.append((str(companhia_id), str(sector_id) if sector_id else None, companhia["setor_atividade"]))
        if sector_id:
            atribuicoes.append(
                {
                    "id": uuid.uuid4(),
                    "companhia_id": companhia_id,
                    "taxonomia": "cvm_cadastro",
                    "setor_id": sector_id,
                    "rotulo_origem": raw[:255],
                    "fonte": "cvm_cadastro",
                    "referencia_fonte": "migration-backfill",
                    "arquivo_origem": (companhia["arquivo_origem"] or "")[:255] or None,
                    "linha_origem": companhia["linha_origem"],
                    "versao_inicio": 1,
                    "inicio_vigencia": agora,
                    "criada_em": agora,
                }
            )
    if atribuicoes:
        atribuicoes_table = sa.table(
            "setor_classificacoes_companhia",
            sa.column("id", sa.Uuid()),
            sa.column("companhia_id", sa.Uuid()),
            sa.column("taxonomia", sa.String(64)),
            sa.column("setor_id", sa.Uuid()),
            sa.column("rotulo_origem", sa.String(255)),
            sa.column("fonte", sa.String(64)),
            sa.column("referencia_fonte", sa.String(255)),
            sa.column("arquivo_origem", sa.String(255)),
            sa.column("linha_origem", sa.Integer()),
            sa.column("versao_inicio", sa.Integer()),
            sa.column("inicio_vigencia", sa.DateTime(timezone=True)),
            sa.column("criada_em", sa.DateTime(timezone=True)),
        )
        bind.execute(sa.insert(atribuicoes_table), atribuicoes)
    payload_semantico = {
        "atribuicoes": sorted(semantic_rows),
        "rotulos": sorted((str(sector_id), labels[key]) for key, sector_id in setores.items()),
    }
    checksum = hashlib.sha256(
        json.dumps(payload_semantico, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    publicacao_id = uuid.uuid4()
    versoes_table = sa.table(
        "setor_taxonomia_versoes",
        sa.column("id", sa.Uuid()),
        sa.column("taxonomia", sa.String(64)),
        sa.column("versao", sa.Integer()),
        sa.column("checksum_fonte", sa.String(64)),
        sa.column("checksum_semantico", sa.String(64)),
        sa.column("referencia_fonte", sa.String(255)),
        sa.column("observada_em", sa.DateTime(timezone=True)),
        sa.column("publicada_em", sa.DateTime(timezone=True)),
        sa.column("resumo", sa.JSON()),
    )
    bind.execute(
        sa.insert(versoes_table),
        {
            "id": publicacao_id,
            "taxonomia": "cvm_cadastro",
            "versao": 1,
            "checksum_fonte": None,
            "checksum_semantico": checksum,
            "referencia_fonte": "migration-backfill",
            "observada_em": None,
            "publicada_em": agora,
            "resumo": {"companhias": len(companhias), "setores": len(labels)},
        },
    )
    if setores:
        mudancas_table = sa.table(
            "setor_taxonomia_mudancas",
            sa.column("id", sa.Uuid()),
            sa.column("publicacao_id", sa.Uuid()),
            sa.column("tipo", sa.String(40)),
            sa.column("setor_id", sa.Uuid()),
            sa.column("depois", sa.JSON()),
            sa.column("criado_em", sa.DateTime(timezone=True)),
        )
        bind.execute(
            sa.insert(mudancas_table),
            [
                {
                    "id": uuid.uuid4(),
                    "publicacao_id": publicacao_id,
                    "tipo": "setor_novo",
                    "setor_id": sector_id,
                    "depois": {"nome": labels[key], "chave_normalizada": key},
                    "criado_em": agora,
                }
                for key, sector_id in setores.items()
            ],
        )
    bind.execute(sa.text(
        "UPDATE setor_taxonomias SET versao_atual=1, checksum_atual=:checksum, "
        "referencia_fonte_atual='migration-backfill', publicada_em=:publicada_em WHERE codigo='cvm_cadastro'"
    ), {"checksum": checksum, "publicada_em": agora})


def downgrade() -> None:
    op.drop_table("setor_taxonomia_mudancas")
    op.drop_table("setor_correspondencias")
    op.drop_table("setor_classificacoes_companhia")
    op.drop_table("setor_aliases")
    op.drop_table("setores")
    op.drop_table("setor_taxonomia_versoes")
    op.drop_table("setor_taxonomias")

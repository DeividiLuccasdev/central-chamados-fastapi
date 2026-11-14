"""Estrutura inicial (a mesma que o antigo create_all gerava)

Bancos criados antes do Alembic já têm estas tabelas: o script
`python -m scripts.criar_tabelas` detecta isso e marca esta revisão como
aplicada (alembic stamp) antes de seguir para as próximas.

Revision ID: 0001
Revises:
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False, unique=True),
        sa.Column("senha", sa.String(length=255), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=True),
        sa.Column("data_cadastro", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_usuarios_id", "usuarios", ["id"])

    op.create_table(
        "chamados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("prioridade", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column(
            "data_criacao",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("data_atualizacao", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_fechamento", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chamados_id", "chamados", ["id"])


def downgrade() -> None:
    op.drop_index("ix_chamados_id", table_name="chamados")
    op.drop_table("chamados")
    op.drop_index("ix_usuarios_id", table_name="usuarios")
    op.drop_table("usuarios")

"""Concorrência e idempotência

- e-mail único sem diferenciar maiúsculas (índice único em lower(email));
- coluna chamados.versao para o controle de concorrência otimista;
- tabela idempotency_keys para a criação idempotente de chamados.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conexao = op.get_bind()

    # Antes de normalizar, confere se há e-mails que só diferem por maiúsculas
    # ou espaços: o índice único falharia e é melhor explicar o motivo.
    duplicados = conexao.execute(sa.text(
        "SELECT lower(trim(email)) AS email, count(*) AS total "
        "FROM usuarios GROUP BY lower(trim(email)) HAVING count(*) > 1"
    )).all()

    if duplicados:
        lista = ", ".join(f"{linha.email} ({linha.total}x)" for linha in duplicados)
        raise RuntimeError(
            "Existem usuários com o mesmo e-mail variando só maiúsculas/espaços: "
            f"{lista}. Unifique ou altere esses cadastros e rode a migração de novo."
        )

    op.execute("UPDATE usuarios SET email = lower(trim(email))")
    op.create_index(
        "uq_usuarios_email_lower",
        "usuarios",
        [sa.text("lower(email)")],
        unique=True,
    )

    op.add_column(
        "chamados",
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chave", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("usuario_id", "chave", name="uq_idempotency_keys_usuario_chave"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_column("chamados", "versao")
    op.drop_index("uq_usuarios_email_lower", table_name="usuarios")

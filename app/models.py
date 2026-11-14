from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

STATUS_CHAMADO = (
    "aberto",
    "em andamento",
    "resolvido"
)

PRIORIDADES_CHAMADO = (
    "baixa",
    "media",
    "alta"
)

# Transições de status permitidas. Um chamado resolvido só volta a ficar
# aberto por uma reabertura explícita (resolvido -> aberto): um formulário
# antigo pedindo "em andamento" não reabre o chamado sem querer.
TRANSICOES_STATUS = {
    "aberto": {"em andamento", "resolvido"},
    "em andamento": {"aberto", "resolvido"},
    "resolvido": {"aberto"},
}


def normalizar_email(email: str) -> str:
    return email.strip().lower()


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    senha: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool | None] = mapped_column(Boolean, default=True)

    data_cadastro: Mapped[datetime | None] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    chamados: Mapped[list["Chamado"]] = relationship(back_populates="usuario")


# E-mail único sem diferenciar maiúsculas (A@x.com == a@x.com). Quem garante a
# unicidade é o banco, inclusive com dois cadastros simultâneos.
Index("uq_usuarios_email_lower", func.lower(Usuario.email), unique=True)


class Chamado(Base):
    __tablename__ = "chamados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id"))

    # Incrementada a cada alteração de status (controle de concorrência otimista)
    versao: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1"
    )

    data_criacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    data_atualizacao: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    data_fechamento: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    usuario: Mapped[Usuario | None] = relationship(back_populates="chamados")


class ChaveIdempotencia(Base):
    """Resposta já enviada para uma Idempotency-Key, por usuário.

    É gravada na mesma transação do chamado criado: ou os dois existem, ou nenhum.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("usuario_id", "chave", name="uq_idempotency_keys_usuario_chave"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )
    chave: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

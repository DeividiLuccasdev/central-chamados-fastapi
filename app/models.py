from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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


class Chamado(Base):
    __tablename__ = "chamados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    prioridade: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id"))

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

    def alterar_status(self, novo_status: str) -> None:
        """Altera o status e registra as datas de atualização e fechamento."""

        # Registra a alteração somente se o status mudou
        if (self.status or "").strip().lower() == novo_status:
            return

        agora = datetime.now(UTC)

        self.status = novo_status
        self.data_atualizacao = agora

        # Se resolveu, registra a hora de fechamento; se reabriu, remove
        self.data_fechamento = agora if novo_status == "resolvido" else None

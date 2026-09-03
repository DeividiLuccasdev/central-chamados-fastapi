from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)

    nome = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(150),
        unique=True,
        nullable=False
    )

    senha = Column(
        String(255),
        nullable=False
    )

    ativo = Column(
        Boolean,
        default=True
    )

    data_cadastro = Column(
        DateTime,
        server_default=func.now()
    )
class Chamado(Base):
    __tablename__ = "chamados"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    titulo = Column(
        String(150),
        nullable=False
    )

    descricao = Column(
        Text,
        nullable=False
    )

    prioridade = Column(
        String(20),
        nullable=False,
        default="media"
    )

    status = Column(
        String(30),
        nullable=False,
        default="aberto"
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False
    )

    data_criacao = Column(
        DateTime,
        server_default=func.now()
    )
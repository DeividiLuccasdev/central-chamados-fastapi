from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

StatusChamado = Literal["aberto", "em andamento", "resolvido"]
PrioridadeChamado = Literal["baixa", "media", "alta"]


def normalizar_texto(valor):
    if isinstance(valor, str):
        return valor.strip().lower()

    return valor


# Usuários

class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=150)
    senha: str = Field(min_length=6)


class UsuarioLogin(BaseModel):
    email: str
    senha: str


class UsuarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    ativo: bool | None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Chamados

class ChamadoCriar(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str
    prioridade: PrioridadeChamado = "media"

    _normalizar_prioridade = field_validator("prioridade", mode="before")(normalizar_texto)


class ChamadoStatus(BaseModel):
    status: StatusChamado

    _normalizar_status = field_validator("status", mode="before")(normalizar_texto)


class ChamadoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    descricao: str | None
    prioridade: str
    status: str
    usuario_id: int | None
    data_criacao: datetime | None
    data_atualizacao: datetime | None
    data_fechamento: datetime | None

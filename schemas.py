from pydantic import BaseModel, Field


class UsuarioCriar(BaseModel):
    nome: str
    email: str
    senha: str = Field(min_length=6)

class ChamadoCriar(BaseModel):
    titulo: str
    descricao: str
    prioridade: str = "media"

class ChamadoStatus(BaseModel):
    status: str

class UsuarioLogin(BaseModel):
    email: str
    senha: str
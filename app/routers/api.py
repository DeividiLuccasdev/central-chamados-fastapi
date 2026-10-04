"""API REST protegida por JWT. Documentação interativa em /docs."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models
from app.core.security import criar_token, gerar_hash_senha, verificar_senha
from app.database import get_db
from app.dependencies import obter_usuario_api
from app.schemas import (
    ChamadoCriar,
    ChamadoResposta,
    ChamadoStatus,
    PrioridadeChamado,
    StatusChamado,
    Token,
    UsuarioCriar,
    UsuarioLogin,
    UsuarioResposta,
)

router = APIRouter()


def buscar_chamado(db: Session, chamado_id: int) -> models.Chamado:
    chamado = db.get(models.Chamado, chamado_id)

    if not chamado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado"
        )

    return chamado


# Autenticação

@router.post("/login", response_model=Token, tags=["Autenticação"])
def login(
    dados: UsuarioLogin,
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if not usuario or not verificar_senha(dados.senha, usuario.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos"
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este usuário está inativo"
        )

    token = criar_token({
        "sub": str(usuario.id),
        "email": usuario.email
    })

    return Token(access_token=token)


@router.get("/perfil", response_model=UsuarioResposta, tags=["Autenticação"])
def perfil(
    usuario: models.Usuario = Depends(obter_usuario_api)
):
    return usuario


# Usuários

@router.post(
    "/usuarios",
    response_model=UsuarioResposta,
    status_code=status.HTTP_201_CREATED,
    tags=["Usuários"]
)
def criar_usuario(
    dados: UsuarioCriar,
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    existente = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário com este e-mail"
        )

    novo_usuario = models.Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=gerar_hash_senha(dados.senha),
        ativo=True
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario


# Chamados

@router.get("/chamados", response_model=list[ChamadoResposta], tags=["Chamados"])
def listar_chamados(
    status_chamado: StatusChamado | None = Query(None, alias="status"),
    prioridade: PrioridadeChamado | None = None,
    limite: int = Query(50, ge=1, le=200),
    deslocamento: int = Query(0, ge=0),
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    consulta = db.query(models.Chamado)

    if status_chamado:
        consulta = consulta.filter(models.Chamado.status == status_chamado)

    if prioridade:
        consulta = consulta.filter(models.Chamado.prioridade == prioridade)

    return consulta.order_by(
        models.Chamado.data_criacao.desc()
    ).offset(deslocamento).limit(limite).all()


@router.post(
    "/chamados",
    response_model=ChamadoResposta,
    status_code=status.HTTP_201_CREATED,
    tags=["Chamados"]
)
def criar_chamado(
    dados: ChamadoCriar,
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    novo_chamado = models.Chamado(
        titulo=dados.titulo,
        descricao=dados.descricao,
        prioridade=dados.prioridade,
        status="aberto",
        usuario_id=usuario_logado.id
    )

    db.add(novo_chamado)
    db.commit()
    db.refresh(novo_chamado)

    return novo_chamado


@router.get("/chamados/{chamado_id}", response_model=ChamadoResposta, tags=["Chamados"])
def obter_chamado(
    chamado_id: int,
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    return buscar_chamado(db, chamado_id)


@router.patch(
    "/chamados/{chamado_id}/status",
    response_model=ChamadoResposta,
    tags=["Chamados"]
)
def alterar_status_chamado(
    chamado_id: int,
    dados: ChamadoStatus,
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    chamado = buscar_chamado(db, chamado_id)

    chamado.alterar_status(dados.status)

    db.commit()
    db.refresh(chamado)

    return chamado

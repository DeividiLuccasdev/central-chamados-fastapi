"""API REST protegida por JWT. Documentação interativa em /docs."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import models, services
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
    usuario = services.buscar_usuario_por_email(db, dados.email)

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
    try:
        return services.cadastrar_usuario(
            db,
            nome=dados.nome,
            email=dados.email,
            senha_hash=gerar_hash_senha(dados.senha)
        )
    except services.Conflito as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro))


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
    idempotency_key: str | None = Header(
        None,
        description=(
            "Opcional. Reenviar a mesma chave com o mesmo corpo devolve o chamado já "
            "criado em vez de criar outro (útil para repetir após timeout)."
        )
    ),
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    def inserir() -> tuple[int, dict]:
        novo_chamado = models.Chamado(
            titulo=dados.titulo,
            descricao=dados.descricao,
            prioridade=dados.prioridade,
            status="aberto",
            usuario_id=usuario_logado.id
        )

        db.add(novo_chamado)
        db.flush()
        db.refresh(novo_chamado)

        corpo = ChamadoResposta.model_validate(novo_chamado).model_dump(mode="json")
        return status.HTTP_201_CREATED, corpo

    if idempotency_key is None:
        codigo, corpo = inserir()
        db.commit()
        return JSONResponse(content=corpo, status_code=codigo)

    try:
        chave = services.validar_chave(idempotency_key)
        codigo, corpo, repetida = services.executar_idempotente(
            db,
            usuario_id=usuario_logado.id,
            chave=chave,
            dados=dados.model_dump(mode="json"),
            executar=inserir
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))
    except services.ChaveIdempotenciaReutilizada as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(erro)
        )

    return JSONResponse(
        content=corpo,
        status_code=codigo,
        headers={"Idempotent-Replayed": "true" if repetida else "false"}
    )


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
    tags=["Chamados"],
    responses={409: {"description": "Transição não permitida ou chamado alterado por outra pessoa"}}
)
def alterar_status_chamado(
    chamado_id: int,
    dados: ChamadoStatus,
    usuario_logado: models.Usuario = Depends(obter_usuario_api),
    db: Session = Depends(get_db)
):
    chamado = buscar_chamado(db, chamado_id)

    try:
        return services.alterar_status(
            db,
            chamado,
            dados.status,
            status_esperado=dados.status_atual,
            versao_esperada=dados.versao
        )
    except services.Conflito as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro))

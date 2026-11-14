"""Páginas web (Jinja2) autenticadas por sessão."""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import models, services
from app.core.security import gerar_hash_senha, verificar_senha
from app.database import get_db
from app.dependencies import obter_usuario_web
from app.templating import templates

router = APIRouter(include_in_schema=False)


def redirecionar(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def buscar_chamado(db: Session, chamado_id: int) -> models.Chamado:
    chamado = db.get(models.Chamado, chamado_id)

    if not chamado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chamado não encontrado"
        )

    return chamado


def buscar_usuario(db: Session, usuario_id: int) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )

    return usuario


@router.get("/")
def inicio():
    return redirecionar("/dashboard")


# Login e logout

@router.get("/login-web")
def pagina_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"erro": None}
    )


@router.post("/login-web")
def login_web(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario = services.buscar_usuario_por_email(db, email)

    erro = None
    status_code = status.HTTP_200_OK

    if not usuario or not verificar_senha(senha, usuario.senha):
        erro = "E-mail ou senha inválidos"
        status_code = status.HTTP_401_UNAUTHORIZED

    elif not usuario.ativo:
        erro = "Este usuário está inativo"
        status_code = status.HTTP_403_FORBIDDEN

    if erro:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"erro": erro},
            status_code=status_code
        )

    request.session["usuario_id"] = usuario.id
    request.session["usuario_nome"] = usuario.nome

    return redirecionar("/dashboard")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()

    return redirecionar("/login-web")


# Dashboard

@router.get("/dashboard")
def dashboard(
    request: Request,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    def contar(status_chamado: str) -> int:
        return db.query(models.Chamado).filter(
            models.Chamado.status == status_chamado
        ).count()

    chamados = db.query(models.Chamado).order_by(
        models.Chamado.data_criacao.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total": db.query(models.Chamado).count(),
            "abertos": contar("aberto"),
            "em_andamento": contar("em andamento"),
            "resolvidos": contar("resolvido"),
            "chamados": chamados
        }
    )


@router.get("/painel")
def painel():
    return redirecionar("/dashboard")


# Chamados

@router.get("/chamados-web")
def listar_chamados_web(
    request: Request,
    status_chamado: str | None = Query(None, alias="status"),
    prioridade: str | None = None,
    busca: str | None = None,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    consulta = db.query(models.Chamado)

    if status_chamado:
        consulta = consulta.filter(
            models.Chamado.status == status_chamado.lower()
        )

    if prioridade:
        consulta = consulta.filter(
            models.Chamado.prioridade == prioridade.lower()
        )

    if busca:
        consulta = consulta.filter(
            models.Chamado.titulo.icontains(busca, autoescape=True)
        )

    chamados = consulta.order_by(
        models.Chamado.data_criacao.desc()
    ).all()

    titulos_chamados = [
        titulo
        for (titulo,) in db.query(models.Chamado.titulo)
        .distinct()
        .order_by(models.Chamado.titulo.asc())
        .all()
    ]

    return templates.TemplateResponse(
        request=request,
        name="chamados.html",
        context={
            "chamados": chamados,
            "status": status_chamado,
            "prioridade": prioridade,
            "titulos_chamados": titulos_chamados
        }
    )


@router.get("/novo-chamado")
def pagina_novo_chamado(
    request: Request,
    usuario: models.Usuario = Depends(obter_usuario_web)
):
    return templates.TemplateResponse(
        request=request,
        name="novo_chamado.html",
        # Chave de uso único: um duplo clique ou um reenvio do formulário
        # não abre o mesmo chamado duas vezes
        context={"chave_idempotencia": str(uuid.uuid4())}
    )


@router.post("/novo-chamado")
def salvar_novo_chamado(
    titulo: str = Form(...),
    descricao: str = Form(...),
    prioridade: str = Form(...),
    chave_idempotencia: str | None = Form(None),
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    prioridade = prioridade.strip().lower()

    if prioridade not in models.PRIORIDADES_CHAMADO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prioridade inválida"
        )

    dados = {
        "titulo": titulo.strip(),
        "descricao": descricao.strip(),
        "prioridade": prioridade
    }

    def inserir() -> tuple[int, dict]:
        novo_chamado = models.Chamado(**dados, status="aberto", usuario_id=usuario.id)
        db.add(novo_chamado)
        db.flush()
        return status.HTTP_303_SEE_OTHER, {"id": novo_chamado.id}

    if not chave_idempotencia:
        inserir()
        db.commit()
        return redirecionar("/dashboard")

    try:
        services.executar_idempotente(
            db,
            usuario_id=usuario.id,
            # O prefixo separa as chaves do formulário das enviadas pela API
            chave=services.validar_chave("web:" + chave_idempotencia.strip()),
            dados=dados,
            executar=inserir
        )
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro))
    except services.ChaveIdempotenciaReutilizada as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(erro)
        )

    return redirecionar("/dashboard")


@router.get("/chamados/{chamado_id}/ver")
def ver_chamado(
    chamado_id: int,
    request: Request,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="ver_chamado.html",
        context={"chamado": buscar_chamado(db, chamado_id)}
    )


@router.get("/chamados/{chamado_id}/status")
def pagina_alterar_status(
    chamado_id: int,
    request: Request,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        request=request,
        name="alterar_status.html",
        context={"chamado": buscar_chamado(db, chamado_id), "erro": None}
    )


@router.post("/chamados/{chamado_id}/status")
def salvar_status_chamado(
    chamado_id: int,
    request: Request,
    novo_status: str = Form(..., alias="status"),
    status_atual: str | None = Form(None),
    versao: int | None = Form(None),
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    chamado = buscar_chamado(db, chamado_id)

    novo_status = novo_status.strip().lower()

    if novo_status not in models.STATUS_CHAMADO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status inválido"
        )

    try:
        services.alterar_status(
            db,
            chamado,
            novo_status,
            # O formulário envia o status e a versão que estavam na tela
            status_esperado=status_atual.strip().lower() if status_atual else None,
            versao_esperada=versao
        )
    except services.Conflito as erro:
        # Mostra o estado atual do chamado para a pessoa decidir de novo
        return templates.TemplateResponse(
            request=request,
            name="alterar_status.html",
            context={"chamado": buscar_chamado(db, chamado_id), "erro": str(erro)},
            status_code=status.HTTP_409_CONFLICT
        )

    return redirecionar("/dashboard")


# Usuários

@router.get("/usuarios-web")
def listar_usuarios_web(
    request: Request,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    usuarios = db.query(models.Usuario).order_by(
        models.Usuario.nome.asc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="usuarios.html",
        context={
            "usuarios": usuarios,
            "usuario_logado": usuario.id,
            "eh_usuario_demo": services.eh_usuario_demo
        }
    )


@router.get("/novo-usuario")
def pagina_novo_usuario(
    request: Request,
    usuario: models.Usuario = Depends(obter_usuario_web)
):
    return templates.TemplateResponse(
        request=request,
        name="novo_usuario.html",
        context={"erro": None}
    )


@router.post("/novo-usuario")
def salvar_novo_usuario(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    erro = None

    if len(senha) < 6:
        erro = "A senha deve ter pelo menos 6 caracteres."

    else:
        try:
            services.cadastrar_usuario(
                db,
                nome=nome.strip(),
                email=email,
                senha_hash=gerar_hash_senha(senha)
            )
        except services.Conflito:
            erro = "Já existe um usuário com este e-mail."

    if erro:
        return templates.TemplateResponse(
            request=request,
            name="novo_usuario.html",
            context={"erro": erro},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    return redirecionar("/dashboard")


@router.post("/usuarios/{usuario_id}/inativar")
def inativar_usuario(
    usuario_id: int,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    if usuario_id == usuario.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode inativar seu próprio usuário."
        )

    buscar_usuario(db, usuario_id)

    try:
        services.inativar_usuario(db, ator_id=usuario.id, alvo_id=usuario_id)
    except services.UsuarioProtegido as erro:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(erro))
    except services.Conflito as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro))

    return redirecionar("/usuarios-web")


@router.post("/usuarios/{usuario_id}/ativar")
def ativar_usuario(
    usuario_id: int,
    usuario: models.Usuario = Depends(obter_usuario_web),
    db: Session = Depends(get_db)
):
    buscar_usuario(db, usuario_id).ativo = True
    db.commit()

    return redirecionar("/usuarios-web")

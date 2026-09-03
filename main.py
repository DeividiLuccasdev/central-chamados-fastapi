import jwt
import models
import os


from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Usuario
from schemas import UsuarioCriar, UsuarioLogin, ChamadoCriar, ChamadoStatus
from pwdlib import PasswordHash
from schemas import UsuarioLogin
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET_KEY")
)
templates = Jinja2Templates(directory="templates")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(
    directory="templates"
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/")
def inicio():
    return {"mensagem": "Central de Chamados funcionando!"}


password_hash = PasswordHash.recommended()


SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
TEMPO_TOKEN_MINUTOS = 60

security = HTTPBearer()


def verificar_token(
    credenciais: HTTPAuthorizationCredentials = Depends(security)
):
    token = credenciais.credentials

    try:
        dados = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return dados

    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado"
        )

def criar_token(dados: dict):
    dados_token = dados.copy()

    expiracao = datetime.now(timezone.utc) + timedelta(
        minutes=TEMPO_TOKEN_MINUTOS
    )

    dados_token.update({
        "exp": expiracao
    })

    token = jwt.encode(
        dados_token,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


def validar_token(
    credenciais: HTTPAuthorizationCredentials = Depends(security)
):
    token = credenciais.credentials

    try:
        dados = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return dados

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado"
        )


@app.post("/usuarios")
def criar_usuario(
    usuario: UsuarioCriar,
    usuario_token: dict = Depends(validar_token),
    db: Session = Depends(get_db)
):
    novo_usuario = models.Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha=password_hash.hash(usuario.senha),
        ativo=True
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return {
        "id": novo_usuario.id,
        "nome": novo_usuario.nome,
        "email": novo_usuario.email
    }

@app.post("/login")
def login(
    dados: UsuarioLogin,
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos"
        )

    if not password_hash.verify(dados.senha, usuario.senha):
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos"
        )

    token = criar_token({
        "sub": str(usuario.id),
        "email": usuario.email
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }
@app.get("/protegida")
def rota_protegida(
    usuario_token: dict = Depends(validar_token)
):
    return {
        "mensagem": "Acesso autorizado!",
        "usuario": usuario_token
    }
@app.get("/perfil")
def perfil(
    dados_token: dict = Depends(verificar_token)
):
    return {
        "mensagem": "Acesso autorizado",
        "usuario_id": dados_token["sub"],
        "email": dados_token["email"]
    }

@app.post("/chamados")
def criar_chamado(
    chamado: ChamadoCriar,
    usuario_token: dict = Depends(validar_token),
    db: Session = Depends(get_db)
):
    novo_chamado = models.Chamado(
        titulo=chamado.titulo,
        descricao=chamado.descricao,
        prioridade=chamado.prioridade,
        status="aberto",
        usuario_id=int(usuario_token["sub"])
    )

    db.add(novo_chamado)
    db.commit()
    db.refresh(novo_chamado)

    return {
        "id": novo_chamado.id,
        "titulo": novo_chamado.titulo,
        "descricao": novo_chamado.descricao,
        "prioridade": novo_chamado.prioridade,
        "status": novo_chamado.status,
        "usuario_id": novo_chamado.usuario_id
    }

@app.get("/chamados/{chamado_id}/ver")
def ver_chamado(
    chamado_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    chamado = db.query(models.Chamado).filter(
        models.Chamado.id == chamado_id
    ).first()

    if not chamado:
        raise HTTPException(
            status_code=404,
            detail="Chamado não encontrado"
        )

    return templates.TemplateResponse(
        request=request,
        name="ver_chamado.html",
        context={
            "chamado": chamado
        }
    )

@app.patch("/chamados/{chamado_id}/status")
def alterar_status_chamado(
    chamado_id: int,
    dados: ChamadoStatus,
    usuario_token: dict = Depends(validar_token),
    db: Session = Depends(get_db)
):
    chamado = db.query(models.Chamado).filter(
        models.Chamado.id == chamado_id
    ).first()

    if not chamado:
        raise HTTPException(
            status_code=404,
            detail="Chamado não encontrado"
        )

    status_permitidos = [
        "aberto",
        "em andamento",
        "resolvido"
    ]

    if dados.status.lower() not in status_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Status inválido"
        )

    chamado.status = dados.status.lower()

    db.commit()
    db.refresh(chamado)

    return {
        "id": chamado.id,
        "titulo": chamado.titulo,
        "status": chamado.status
    }
@app.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    total = db.query(models.Chamado).count()

    abertos = db.query(models.Chamado).filter(
        models.Chamado.status == "aberto"
    ).count()

    em_andamento = db.query(models.Chamado).filter(
        models.Chamado.status == "em andamento"
    ).count()

    resolvidos = db.query(models.Chamado).filter(
        models.Chamado.status == "resolvido"
    ).count()

    chamados = db.query(models.Chamado).order_by(
        models.Chamado.data_criacao.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total": total,
            "abertos": abertos,
            "em_andamento": em_andamento,
            "resolvidos": resolvidos,
            "chamados": chamados
        }
    )

@app.get("/painel")
def painel(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )
@app.get("/chamados/{chamado_id}/status")
def pagina_alterar_status(
    chamado_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    chamado = db.query(models.Chamado).filter(
        models.Chamado.id == chamado_id
    ).first()

    return templates.TemplateResponse(
        request=request,
        name="alterar_status.html",
        context={
            "chamado": chamado
        }
    )
@app.post("/chamados/{chamado_id}/status")
def salvar_status_chamado(
    chamado_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    chamado = db.query(models.Chamado).filter(
        models.Chamado.id == chamado_id
    ).first()

    if not chamado:
        raise HTTPException(
            status_code=404,
            detail="Chamado não encontrado"
        )

    status_permitidos = [
        "aberto",
        "em andamento",
        "resolvido"
    ]

    if status not in status_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Status inválido"
        )

    chamado.status = status

    db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )
@app.get("/novo-chamado")
def pagina_novo_chamado(
    request: Request
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="novo_chamado.html",
        context={}
    )

@app.get("/login-web")
def pagina_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "erro": None
        }
    )


@app.post("/login-web")
def login_web(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == email
    ).first()

    if not usuario:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "erro": "E-mail ou senha inválidos"
            },
            status_code=401
        )

    if not usuario.ativo:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "erro": "Este usuário está inativo"
            },
            status_code=403
        )

    if not password_hash.verify(senha, usuario.senha):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "erro": "E-mail ou senha inválidos"
            },
            status_code=401
        )

    request.session["usuario_id"] = usuario.id
    request.session["usuario_nome"] = usuario.nome

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )
@app.post("/novo-chamado")
def salvar_novo_chamado(
    request: Request,
    titulo: str = Form(...),
    descricao: str = Form(...),
    prioridade: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    novo_chamado = models.Chamado(
        titulo=titulo,
        descricao=descricao,
        prioridade=prioridade,
        status="aberto",
        usuario_id=usuario_id
    )

    db.add(novo_chamado)
    db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )
@app.get("/logout")
def logout(request: Request):
    request.session.clear()

    return RedirectResponse(
        url="/login-web",
        status_code=303
    )
@app.get("/novo-usuario")
def pagina_novo_usuario(
    request: Request
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="novo_usuario.html",
        context={
            "erro": None
        }
    )
@app.post("/novo-usuario")
def salvar_novo_usuario(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )
    if len(senha) < 6:
        return templates.TemplateResponse(
        request=request,
        name="novo_usuario.html",
        context={
            "erro": "A senha deve ter pelo menos 6 caracteres."
        },
        status_code=400
    )

    usuario_existente = db.query(models.Usuario).filter(
        models.Usuario.email == email
    ).first()

    if usuario_existente:
        return templates.TemplateResponse(
            request=request,
            name="novo_usuario.html",
            context={
                "erro": "Já existe um usuário com este e-mail."
            },
            status_code=400
        )

    novo_usuario = models.Usuario(
        nome=nome,
        email=email,
        senha=password_hash.hash(senha),
        ativo=True
    )

    db.add(novo_usuario)
    db.commit()

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )
@app.get("/usuarios-web")
def listar_usuarios_web(
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    usuarios = db.query(models.Usuario).order_by(
        models.Usuario.nome.asc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="usuarios.html",
       context={
    "usuarios": usuarios,
    "usuario_logado": usuario_id
}
    )
@app.post("/usuarios/{usuario_id}/inativar")
def inativar_usuario(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_logado = request.session.get("usuario_id")

    if not usuario_logado:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )
    if usuario_id == usuario_logado:
        raise HTTPException(
        status_code=400,
        detail="Você não pode inativar seu próprio usuário."
    )

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado"
        )

    usuario.ativo = False

    db.commit()

    return RedirectResponse(
        url="/usuarios-web",
        status_code=303
    )


@app.post("/usuarios/{usuario_id}/ativar")
def ativar_usuario(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    usuario_logado = request.session.get("usuario_id")

    if not usuario_logado:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado"
        )

    usuario.ativo = True

    db.commit()

    return RedirectResponse(
        url="/usuarios-web",
        status_code=303
    )
@app.get("/chamados-web")
def listar_chamados_web(
    request: Request,
    status: str | None = None,
    prioridade: str | None = None,
    busca: str | None = None,
    db: Session = Depends(get_db)
):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(
            url="/login-web",
            status_code=303
        )

    consulta = db.query(models.Chamado)

    if status:
        consulta = consulta.filter(
            models.Chamado.status == status.lower()
        )

    if prioridade:
        consulta = consulta.filter(
            models.Chamado.prioridade == prioridade.lower()
        )

    if busca:
        consulta = consulta.filter(
            models.Chamado.titulo.ilike(f"%{busca}%")
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
            "status": status,
            "prioridade": prioridade,
            "titulos_chamados": titulos_chamados
        }
    )
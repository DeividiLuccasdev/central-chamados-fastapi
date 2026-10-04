from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.dependencies import LoginNecessario
from app.routers import api, web
from app.templating import BASE_DIR

app = FastAPI(
    title=settings.app_nome,
    description=(
        "Sistema de gerenciamento de chamados com interface web e API REST.\n\n"
        "Para usar a API, faça login em `POST /login` e envie o token no cabeçalho "
        "`Authorization: Bearer <token>`."
    ),
    version="1.0.0"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key,
    https_only=settings.cookie_https_only,
    same_site="lax"
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

app.include_router(web.router)
app.include_router(api.router)


@app.exception_handler(LoginNecessario)
def redirecionar_para_login(request: Request, exc: LoginNecessario):
    return RedirectResponse(url="/login-web", status_code=303)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Configurações da aplicação, lidas das variáveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore"
    )

    app_nome: str = "Central de Chamados"

    # Banco online (Neon / Render). Se não for informado, usa as variáveis DB_*.
    database_url: str | None = None

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "central_chamados"
    db_user: str = "postgres"
    db_password: str = ""

    # Obrigatória: a aplicação não sobe sem ela
    jwt_secret_key: str
    jwt_algoritmo: str = "HS256"
    jwt_expiracao_minutos: int = 60

    # Cookie de sessão só via HTTPS. Se não for informado, é ligado
    # automaticamente no Render (que define RENDER=true em todo serviço).
    session_https_only: bool | None = None
    render: bool = False

    @property
    def cookie_https_only(self) -> bool:
        if self.session_https_only is not None:
            return self.session_https_only

        return self.render

    @property
    def url_banco(self) -> str | URL:
        if self.database_url:
            return self.database_url

        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

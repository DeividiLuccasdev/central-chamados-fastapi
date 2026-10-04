from datetime import UTC
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def horario_brasil(data):
    """Filtro Jinja: exibe a data no fuso de São Paulo (datas sem fuso são tratadas como UTC)."""

    if not data:
        return "-"

    if data.tzinfo is None:
        data = data.replace(tzinfo=UTC)

    return data.astimezone(FUSO_BRASIL).strftime("%d/%m/%Y %H:%M")


templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["horario_brasil"] = horario_brasil

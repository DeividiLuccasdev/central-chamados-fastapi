from app.core.config import Settings


def configurar(monkeypatch, **variaveis):
    for nome in ("RENDER", "SESSION_HTTPS_ONLY"):
        monkeypatch.delenv(nome, raising=False)

    for nome, valor in variaveis.items():
        monkeypatch.setenv(nome, valor)

    return Settings(_env_file=None)


def test_cookie_https_desligado_localmente(monkeypatch):
    assert configurar(monkeypatch).cookie_https_only is False


def test_cookie_https_ligado_automaticamente_no_render(monkeypatch):
    assert configurar(monkeypatch, RENDER="true").cookie_https_only is True


def test_variavel_explicita_tem_prioridade(monkeypatch):
    configuracao = configurar(monkeypatch, RENDER="true", SESSION_HTTPS_ONLY="false")

    assert configuracao.cookie_https_only is False


def test_variaveis_vazias_sao_ignoradas(monkeypatch):
    configuracao = configurar(monkeypatch, RENDER="", SESSION_HTTPS_ONLY="")

    assert configuracao.cookie_https_only is False

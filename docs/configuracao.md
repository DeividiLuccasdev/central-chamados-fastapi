# Variáveis de ambiente

As configurações são lidas do ambiente ou de um arquivo `.env` na raiz (`app/core/config.py`, com pydantic-settings). Use o `.env.example` como base.

| Variável | Obrigatória | Descrição |
|---|---|---|
| `JWT_SECRET_KEY` | Sim | Chave usada para assinar os tokens JWT e o cookie de sessão. A aplicação não sobe sem ela |
| `DATABASE_URL` | Não | URL completa do banco (Neon / Render). Tem prioridade sobre as variáveis `DB_*` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Não | Dados do banco local |
| `JWT_EXPIRACAO_MINUTOS` | Não | Validade do token (padrão: 60) |
| `SESSION_HTTPS_ONLY` | Não | Cookie de sessão só via HTTPS. Se não for informada, é ativada automaticamente no Render |

Para gerar uma `JWT_SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

O Render define `RENDER=true` em todo serviço; é essa variável que liga o cookie seguro quando `SESSION_HTTPS_ONLY` não é informada. Localmente (`http://127.0.0.1`), deixe `SESSION_HTTPS_ONLY=false`.

Nos testes, `TEST_DATABASE_URL` aponta para um PostgreSQL descartável usado pelos testes de concorrência (veja [Testes](testes.md)).

# Testes

Os testes usam **Pytest** e cobrem a API, as páginas web, as regras de concorrência, a configuração, os scripts e o login de demonstração. A suíte coleta 106 testes: 95 rodam com SQLite em memória, sem precisar de PostgreSQL, e 11 (`testes/test_postgres.py`, marcador `pg`) exigem um PostgreSQL de verdade.

Para executar os testes e o lint:

```bash
pytest
ruff check .
```

Sem `TEST_DATABASE_URL`, os testes `pg` são pulados. Para rodá-los, aponte a variável para um banco descartável (o schema é apagado e recriado pelas migrações):

```bash
docker run -d --name pg-teste -e POSTGRES_PASSWORD=postgres -p 5433:5432 postgres:17
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/postgres pytest -m pg
```

Esses testes disparam requisições simultâneas, cada uma com sua própria conexão, e usam uma barreira para que todas leiam o mesmo estado antes de qualquer uma escrever. Veja [Concorrência e idempotência](concorrencia.md).

| Arquivo | O que cobre |
|---|---|
| `testes/test_api.py` | Rotas da API REST: login, token, usuários e chamados |
| `testes/test_web.py` | Páginas web, login, cadastro, ativação e inativação de usuários |
| `testes/test_concorrencia.py` | Transições de status, versão, e-mail e idempotência (SQLite) |
| `testes/test_postgres.py` | Corridas reais contra PostgreSQL |
| `testes/test_config.py` | Leitura das configurações e cookie seguro no Render |
| `testes/test_scripts.py` | Criação de usuário e redefinição de senha pelo script |

## CI

A cada push na `main` e em todo pull request, o **GitHub Actions** (`.github/workflows/ci.yml`) executa o lint com ruff, todos os testes (com um serviço PostgreSQL 17, então os testes `pg` também rodam) e o build da imagem Docker.

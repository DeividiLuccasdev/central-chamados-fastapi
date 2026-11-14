# Execução local

Pré-requisitos: Python 3.11 ou superior (a imagem Docker e o CI usam 3.14) e um PostgreSQL acessível.

Clone o repositório e entre na pasta:

```bash
git clone https://github.com/DeividiLuccasdev/central-chamados-fastapi.git
cd central-chamados-fastapi
```

Crie e ative um ambiente virtual (no Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências (as de desenvolvimento incluem pytest e ruff):

```bash
pip install -r requirements-dev.txt
```

Crie um arquivo `.env` baseado no `.env.example` e configure as variáveis necessárias ([referência](configuracao.md)).

Crie (ou atualize) as tabelas aplicando as migrações:

```bash
python -m scripts.criar_tabelas
```

> As tabelas são versionadas com **Alembic** (pasta `migracoes/`). Bancos criados antes das migrações são reconhecidos automaticamente: a revisão inicial é marcada como aplicada e só as novas rodam. Se a migração avisar que há e-mails repetidos variando só maiúsculas, unifique esses cadastros e rode de novo.

Para conferir a conexão com o banco configurado:

```bash
python -m scripts.verificar_conexao
```

Crie o primeiro usuário (a senha é pedida no terminal):

```bash
python -m scripts.criar_usuario --email voce@exemplo.com --nome "Seu Nome"
```

> O mesmo comando redefine a senha de um usuário que já existe (e o reativa). Pelo sistema, só um usuário logado pode cadastrar outros.

Inicie o servidor:

```bash
uvicorn app.main:app --reload
```

Acesse:

- Sistema: http://127.0.0.1:8000/login-web
- Documentação da API: http://127.0.0.1:8000/docs

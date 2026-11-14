# Docker e deploy

## Docker

Para criar a imagem:

```bash
docker build -t central-chamados-fastapi .
```

Para executar o container:

```bash
docker run -p 8000:8000 --env-file .env central-chamados-fastapi
```

A imagem usa `python:3.14-slim`, roda com um usuário sem privilégios de root (`appuser`) e não inclui `.env`, testes nem screenshots (`.dockerignore`).

O container aplica as migrações pendentes (`python -m scripts.criar_tabelas`) antes de subir a API, então cada deploy no Render já chega com o banco atualizado. Se a migração falhar, a API não sobe e a versão anterior continua no ar.

Em seguida, `python -m scripts.criar_usuario_demo` cria ou restaura o login de demonstração publicado no README (só no Render ou com `CRIAR_USUARIO_DEMO=true`): se a conta já existir, ela é reativada e a senha volta ao valor conhecido. Uma falha nesse passo é registrada no log, mas não impede a API de subir.

O uvicorn roda com `--proxy-headers`, para respeitar o HTTPS informado pelo proxy do Render, e escuta na porta da variável `PORT` (padrão: 8000).

## Deploy

A aplicação está publicada utilizando:

- **Render** para hospedagem da aplicação, a partir do `Dockerfile`
- **Neon PostgreSQL** para o banco de dados em produção, via `DATABASE_URL`
- **Docker** para containerização

[Acessar aplicação online](https://central-chamados-fastapi.onrender.com/login-web)

> O primeiro acesso pode demorar de 30 a 60 segundos. A aplicação usa o plano gratuito do Render, que "adormece" o servidor após 15 minutos sem uso. Depois que ele acorda, tudo responde normalmente.

No Render, o cookie de sessão seguro (`HTTPS only`) é ativado automaticamente; veja [Variáveis de ambiente](configuracao.md).

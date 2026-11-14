# API REST

A API é servida pela mesma aplicação FastAPI da interface web. A documentação interativa (OpenAPI/Swagger) fica em `/docs`.

## Autenticação

Faça login em `POST /login` e envie o token recebido no cabeçalho `Authorization: Bearer <token>`. O token é um JWT assinado com `JWT_SECRET_KEY` e expira após `JWT_EXPIRACAO_MINUTOS` (padrão: 60). Usuários inativados perdem o acesso mesmo com um token ainda dentro da validade.

## Rotas

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/login` | Gera o token de acesso |
| `GET` | `/perfil` | Dados do usuário autenticado |
| `POST` | `/usuarios` | Cadastra um usuário |
| `GET` | `/chamados` | Lista chamados (filtros: `status`, `prioridade`; paginação: `limite`, `deslocamento`) |
| `POST` | `/chamados` | Abre um chamado (aceita o cabeçalho opcional `Idempotency-Key`) |
| `GET` | `/chamados/{id}` | Detalhes de um chamado |
| `PATCH` | `/chamados/{id}/status` | Altera o status (`aberto`, `em andamento`, `resolvido`); aceita `status_atual` e `versao` opcionais e retorna `409` se o chamado mudou |
| `GET` | `/health` | Verificação de saúde da aplicação |

Em `GET /chamados`, `limite` vai de 1 a 200 (padrão: 50) e o resultado vem do chamado mais recente para o mais antigo.

## Alteração segura de status

O cliente informa o que viu ao montar a tela:

```json
{"status": "resolvido", "status_atual": "em andamento", "versao": 2}
```

Se o chamado mudou desde então, a resposta é `409` em vez de sobrescrever a alteração de outra pessoa. As transições permitidas e as demais garantias estão em [Concorrência e idempotência](concorrencia.md).

## Abertura idempotente de chamado

Com o cabeçalho `Idempotency-Key` (1 a 255 caracteres), repetir a mesma requisição devolve o mesmo chamado, sem criar outro. A mesma chave com outro conteúdo retorna `422`. As chaves são separadas por usuário.

## Respostas de erro comuns

| Código | Quando |
|---|---|
| `401` | Credenciais de login incorretas, ou token inválido, expirado ou de usuário inativado |
| `403` | Login de um usuário inativo |
| `404` | Chamado não encontrado |
| `409` | E-mail já cadastrado, chamado alterado por outra pessoa ou transição de status não permitida |
| `422` | Dados inválidos ou `Idempotency-Key` reutilizada com outro conteúdo |

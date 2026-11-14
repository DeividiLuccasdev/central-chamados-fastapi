# Concorrência e idempotência

As regras abaixo ficam em `app/services.py` e são usadas tanto pela API quanto pela interface web, para que as duas portas de entrada tenham as mesmas garantias. O schema correspondente é criado pela migração `migracoes/versions/0002_concorrencia_idempotencia.py`.

- **Status com controle otimista**: cada chamado tem uma `versao`. A alteração de status é um `UPDATE` condicional (`WHERE status = ... AND versao = ...`); se outra pessoa alterou o chamado nesse meio-tempo, nenhuma linha é atualizada e a resposta é **409** em vez de sobrescrever.
- **Transições permitidas**: `aberto ⇄ em andamento`, `aberto/em andamento → resolvido` e `resolvido → aberto` (reabertura explícita). Um formulário antigo pedindo "em andamento" não reabre um chamado resolvido. Pedir o status que o chamado já tem não altera nada.
- **Datas pelo relógio do banco** (`now()`), o mesmo usado em `data_criacao`. Ao resolver, `data_fechamento` é preenchida; ao reabrir, é removida.
- **E-mail único sem diferenciar maiúsculas**: gravado em minúsculas e protegido por um índice único em `lower(email)`. Dois cadastros simultâneos resultam em um **201** e um **409**, nunca em erro 500. A consulta prévia só gera a mensagem amigável; quem garante a unicidade é o índice.
- **Abertura de chamado idempotente**: com o cabeçalho `Idempotency-Key`, repetir a requisição devolve o mesmo chamado; a mesma chave com outro conteúdo retorna **422**. A chave, o hash SHA-256 do conteúdo e a resposta são gravados no mesmo commit do chamado. Se duas requisições com a mesma chave chegarem juntas, o índice único faz a segunda falhar; ela desfaz o que criou e devolve a resposta da primeira. O formulário web envia uma chave de uso único e desabilita o botão após o envio.
- **Sempre há um usuário ativo**: a inativação trava as linhas dos usuários ativos (`SELECT ... FOR UPDATE`, em ordem de id para evitar deadlock), então os dois últimos ativos não conseguem se inativar ao mesmo tempo.

## Como isso é testado

`testes/test_concorrencia.py` cobre as regras com SQLite em memória. `testes/test_postgres.py` (marcador `pg`) dispara requisições simultâneas em threads, cada uma com sua própria conexão, contra um PostgreSQL de verdade. Uma barreira (`threading.Barrier`) segura as requisições logo depois da leitura, para que todas vejam o mesmo estado antes de qualquer uma escrever: a corrida acontece sempre, e não só por sorte do agendador. Veja [Testes](testes.md).

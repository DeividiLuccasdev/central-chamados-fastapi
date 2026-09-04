# 🎫 Central de Chamados - FastAPI

Sistema web para gerenciamento de chamados desenvolvido com Python, FastAPI e PostgreSQL.

O projeto foi criado com foco em estudos de desenvolvimento backend e construção de portfólio, utilizando autenticação, gerenciamento de usuários, filtros, pesquisa e controle de chamados.

## 🌐 Sistema Online

[![Acessar Sistema](https://img.shields.io/badge/Acessar%20Sistema-Online-success?style=for-the-badge)](https://central-chamados-fastapi.onrender.com/login-web)
---

## 🚀 Funcionalidades

- Login de usuários
- Controle de sessão
- Cadastro de usuários
- Ativação e inativação de usuários
- Proteção contra inativar a própria conta
- Cadastro de chamados
- Listagem de chamados
- Visualização de detalhes do chamado
- Alteração de status
- Filtro por status
- Filtro por prioridade
- Pesquisa por título
- Autocomplete na pesquisa
- Dashboard com indicadores
- Validação de senha
- API REST protegida com JWT

---

## 🛠️ Tecnologias utilizadas

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- JWT
- Argon2
- Jinja2
- HTML
- CSS
- JavaScript

---

## 📊 Dashboard

O sistema possui um dashboard com indicadores de:

- Total de chamados
- Chamados abertos
- Chamados em andamento
- Chamados resolvidos

Também apresenta os chamados mais recentes.

---

## 👤 Usuários

O módulo de usuários permite:

- Cadastrar novos usuários
- Ativar usuários
- Inativar usuários
- Visualizar status da conta
- Impedir que o usuário logado inative a própria conta

As senhas são armazenadas utilizando hash com Argon2.

---

## 🎫 Chamados

Cada chamado possui:

- Título
- Descrição
- Prioridade
- Status
- Usuário responsável
- Data de criação

Os chamados podem ser pesquisados e filtrados por:

- Título
- Status
- Prioridade

---

## 🔐 Segurança

O projeto possui:

- Hash de senhas com Argon2
- Autenticação JWT para API
- Sessões para interface web
- Rotas protegidas
- Validação de usuários ativos
- Validação de senha mínima
- Variáveis sensíveis armazenadas em `.env`
- `.env` protegido pelo `.gitignore`

---

## ⚙️ Como executar o projeto

Clone o repositório:

```bash
git clone https://github.com/DeividiLuccasdev/central-chamados-fastapi.git
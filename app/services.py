"""Regras de negócio que precisam ser seguras com requisições simultâneas.

As rotas da API e da interface web usam as mesmas funções, para que as duas
portas de entrada tenham exatamente as mesmas garantias.
"""

import hashlib
import json
from collections.abc import Callable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models

TAMANHO_MAXIMO_CHAVE = 255


class Conflito(Exception):
    """O estado no banco não é o esperado por quem fez a requisição (HTTP 409)."""


class ChaveIdempotenciaReutilizada(Exception):
    """A mesma Idempotency-Key foi enviada com outro conteúdo (HTTP 422)."""


# E-mail

def buscar_usuario_por_email(db: Session, email: str) -> models.Usuario | None:
    # lower() também encontra cadastros antigos gravados com maiúsculas
    return db.scalars(
        select(models.Usuario)
        .where(func.lower(models.Usuario.email) == models.normalizar_email(email))
        .limit(1)
    ).first()


def email_em_uso(db: Session, email: str) -> bool:
    return buscar_usuario_por_email(db, email) is not None


def cadastrar_usuario(db: Session, nome: str, email: str, senha_hash: str) -> models.Usuario:
    """Cadastra um usuário. Lança Conflito se o e-mail já existir.

    A consulta prévia só gera uma mensagem amigável no caso comum; quem garante
    a unicidade é o índice único em lower(email). Se dois cadastros com o mesmo
    e-mail chegarem juntos, o segundo recebe IntegrityError e vira Conflito.
    """

    email = models.normalizar_email(email)

    if email_em_uso(db, email):
        raise Conflito("Já existe um usuário com este e-mail")

    usuario = models.Usuario(nome=nome, email=email, senha=senha_hash, ativo=True)
    db.add(usuario)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Já existe um usuário com este e-mail")

    db.refresh(usuario)
    return usuario


# Status do chamado

def alterar_status(
    db: Session,
    chamado: models.Chamado,
    novo_status: str,
    status_esperado: str | None = None,
    versao_esperada: int | None = None,
) -> models.Chamado:
    """Altera o status com controle de concorrência otimista.

    - status_esperado / versao_esperada: o que o cliente viu ao montar a tela.
      Se o chamado mudou desde então, lança Conflito em vez de sobrescrever.
    - Só aceita as transições de TRANSICOES_STATUS.
    - O UPDATE é condicional (WHERE status = ... AND versao = ...): se outra
      requisição alterou o chamado entre a leitura e a escrita, nenhuma linha é
      atualizada e a operação vira Conflito, sem perder a alteração alheia.
    - As datas vêm do relógio do banco (func.now()), o mesmo de data_criacao.
    """

    if status_esperado is not None and chamado.status != status_esperado:
        raise Conflito(
            f"O chamado está '{chamado.status}', e não '{status_esperado}'. "
            "Ele foi alterado por outra pessoa; recarregue e tente de novo."
        )

    if versao_esperada is not None and chamado.versao != versao_esperada:
        raise Conflito(
            "O chamado foi alterado por outra pessoa; recarregue e tente de novo."
        )

    # Pedir o status que o chamado já tem não muda nada (idempotente)
    if novo_status == chamado.status:
        return chamado

    if novo_status not in models.TRANSICOES_STATUS.get(chamado.status, set()):
        raise Conflito(
            f"Não é permitido mudar o status de '{chamado.status}' para '{novo_status}'."
        )

    resultado = db.execute(
        update(models.Chamado)
        .where(
            models.Chamado.id == chamado.id,
            models.Chamado.status == chamado.status,
            models.Chamado.versao == chamado.versao,
        )
        .values(
            status=novo_status,
            versao=models.Chamado.versao + 1,
            data_atualizacao=func.now(),
            # Ao resolver registra o fechamento; ao reabrir, remove
            data_fechamento=func.now() if novo_status == "resolvido" else None,
        )
        .execution_options(synchronize_session=False)
    )

    if resultado.rowcount != 1:
        db.rollback()
        raise Conflito(
            "O chamado foi alterado por outra pessoa ao mesmo tempo; recarregue e tente de novo."
        )

    db.commit()
    db.refresh(chamado)
    return chamado


# Idempotência

def validar_chave(chave: str) -> str:
    chave = chave.strip()

    if not chave or len(chave) > TAMANHO_MAXIMO_CHAVE:
        raise ValueError(
            f"Idempotency-Key deve ter entre 1 e {TAMANHO_MAXIMO_CHAVE} caracteres"
        )

    return chave


def hash_requisicao(dados: dict) -> str:
    conteudo = json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(conteudo.encode()).hexdigest()


def _buscar_chave(db: Session, usuario_id: int, chave: str) -> models.ChaveIdempotencia | None:
    return db.scalars(
        select(models.ChaveIdempotencia).where(
            models.ChaveIdempotencia.usuario_id == usuario_id,
            models.ChaveIdempotencia.chave == chave,
        )
    ).first()


def _repetir(registro: models.ChaveIdempotencia, request_hash: str) -> tuple[int, dict]:
    if registro.request_hash != request_hash:
        raise ChaveIdempotenciaReutilizada(
            "Esta Idempotency-Key já foi usada com outro conteúdo"
        )

    return registro.status_code, registro.response_json


def executar_idempotente(
    db: Session,
    usuario_id: int,
    chave: str,
    dados: dict,
    executar: Callable[[], tuple[int, dict]],
) -> tuple[int, dict, bool]:
    """Executa `executar` uma única vez por (usuario_id, chave).

    `executar` adiciona os objetos na sessão sem dar commit e retorna
    (status_code, corpo). A chave e o resultado são gravados no mesmo commit.

    Retorna (status_code, corpo, repetida). Mesma chave e mesmo conteúdo devolvem
    a resposta guardada; mesma chave e outro conteúdo lançam
    ChaveIdempotenciaReutilizada. Se duas requisições com a mesma chave chegarem
    juntas, o índice único faz a segunda falhar; ela desfaz o que criou e
    devolve a resposta da primeira.
    """

    request_hash = hash_requisicao(dados)

    registro = _buscar_chave(db, usuario_id, chave)
    if registro:
        return *_repetir(registro, request_hash), True

    status_code, corpo = executar()

    db.add(models.ChaveIdempotencia(
        usuario_id=usuario_id,
        chave=chave,
        request_hash=request_hash,
        status_code=status_code,
        response_json=corpo,
    ))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        registro = _buscar_chave(db, usuario_id, chave)
        if registro is None:
            raise

        return *_repetir(registro, request_hash), True

    return status_code, corpo, False


# Usuários

def inativar_usuario(db: Session, ator_id: int, alvo_id: int) -> None:
    """Inativa `alvo_id` garantindo que sempre sobra pelo menos um usuário ativo.

    Sem trava, os dois últimos usuários ativos podiam se inativar ao mesmo tempo
    (cada um ainda via o outro como ativo) e ninguém mais conseguiria entrar.
    Aqui as linhas dos usuários ativos são travadas (SELECT ... FOR UPDATE, em
    ordem de id para evitar deadlock): a segunda requisição espera a primeira
    terminar e só então confere se quem pede ainda está ativo.
    """

    if ator_id == alvo_id:
        raise ValueError("Você não pode inativar seu próprio usuário.")

    ativos = set(db.scalars(
        select(models.Usuario.id)
        .where(models.Usuario.ativo.is_(True))
        .order_by(models.Usuario.id)
        .with_for_update()
    ))

    if ator_id not in ativos:
        db.rollback()
        raise Conflito("Seu usuário foi inativado por outra pessoa.")

    if alvo_id not in ativos:
        # Já está inativo: nada a fazer (idempotente)
        db.rollback()
        return

    if len(ativos - {alvo_id}) < 1:
        db.rollback()
        raise Conflito("É preciso manter pelo menos um usuário ativo.")

    db.execute(
        update(models.Usuario)
        .where(models.Usuario.id == alvo_id)
        .values(ativo=False)
    )
    db.commit()

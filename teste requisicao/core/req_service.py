# core/req_service.py
"""
Camada de serviço do domínio REQUERIMENTO.

Toda regra de negócio vive aqui. As rotas (core/req_routes.py) são finas:
validam entrada, chamam o serviço e devolvem JSON/HTML.

Princípios aplicados:
- gravação sempre dentro de uma transação (requerimento + filhos + histórico);
- numeração de documento com lock na tabela de controle (nunca MAX(numero)+1);
- dinheiro/quantidade em Decimal;
- nada de exclusão física do documento: cancelamento com trilha;
- validação no servidor independente do JavaScript.
"""

from __future__ import annotations

import os
import re
import unicodedata
import uuid
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_

from core.extensoes import db
from core.req_models import (
    ETAPAS,
    EXTENSOES_ANEXO,
    PAPEIS,
    PRIORIDADES,
    STATUS,
    STATUS_ABERTOS,
    TAMANHO_MAX_ANEXO,
    TIPOS_MOVIMENTO,
    TIPOS_REQUERIMENTO,
    TRANSICOES,
    ReqAnexo,
    ReqComplemento,
    ReqCotacao,
    ReqHistorico,
    ReqItem,
    ReqLocalizacao,
    ReqSequencia,
    ReqUsuarioPapel,
    Requerimento,
)

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANEXOS_DIR = os.path.join(BASE_PATH, "storage", "anexos")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------------------
# EXCEÇÕES DE DOMÍNIO
# ---------------------------------------------------------------------------

class ErroRequerimento(Exception):
    """Erro de negócio previsto; a rota devolve 400 com a mensagem."""

    def __init__(self, mensagem: str, campos: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campos = campos or {}


class AcessoNegado(ErroRequerimento):
    pass


# ---------------------------------------------------------------------------
# PERMISSÕES
# ---------------------------------------------------------------------------

def papel_do_usuario(usuario) -> str:
    """ADMINISTRADOR / ATENDENTE / SOLICITANTE.

    Não altera a tabela `usuarios` existente: usa req_usuario_papel quando houver
    registro e, na ausência, deriva do campo ADM já existente.
    """
    registro = ReqUsuarioPapel.query.filter_by(usuario_id=usuario.id).first()
    if registro and registro.papel in PAPEIS:
        return registro.papel
    if str(getattr(usuario, "ADM", "N")).strip().upper() == "S":
        return "ADMINISTRADOR"
    return "SOLICITANTE"


def pode_ver(requerimento: Requerimento, usuario) -> bool:
    papel = papel_do_usuario(usuario)
    if papel in ("ADMINISTRADOR", "ATENDENTE"):
        return True
    return requerimento.solicitante_usuario_id == usuario.id


def pode_editar(requerimento: Requerimento, usuario) -> bool:
    """Somente rascunho é editável, e só pelo dono (ou administrador)."""
    if requerimento.status != "RASCUNHO":
        return False
    papel = papel_do_usuario(usuario)
    if papel == "ADMINISTRADOR":
        return True
    return requerimento.solicitante_usuario_id == usuario.id


def pode_alterar_status(usuario) -> bool:
    return papel_do_usuario(usuario) in ("ADMINISTRADOR", "ATENDENTE")


def exigir_visualizacao(requerimento: Requerimento, usuario) -> None:
    if not pode_ver(requerimento, usuario):
        raise AcessoNegado("Você não tem permissão para acessar este requerimento.")


def exigir_edicao(requerimento: Requerimento, usuario) -> None:
    exigir_visualizacao(requerimento, usuario)
    if not pode_editar(requerimento, usuario):
        raise AcessoNegado(
            "Este requerimento não pode mais ser editado (somente rascunhos são editáveis)."
        )


# ---------------------------------------------------------------------------
# CONVERSÕES SEGURAS
# ---------------------------------------------------------------------------

def _txt(valor, limite: int | None = None) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    return texto[:limite] if limite else texto


def _dec(valor, campo: str, obrigatorio: bool = False) -> Decimal | None:
    if valor is None or str(valor).strip() == "":
        if obrigatorio:
            raise ErroRequerimento(f"Informe {campo}.", {campo: "obrigatório"})
        return None
    texto = str(valor).strip().replace(".", "").replace(",", ".") if _br_number(valor) else str(valor).strip()
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        raise ErroRequerimento(f"Valor inválido em {campo}.", {campo: "inválido"})


def _br_number(valor) -> bool:
    """True quando o número chega no formato brasileiro (1.234,56)."""
    texto = str(valor)
    return "," in texto


def _data(valor, campo: str) -> date | None:
    if valor is None or str(valor).strip() == "":
        return None
    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(texto[:len(formato) + 2] if "T" in formato else texto, formato).date()
        except ValueError:
            continue
    raise ErroRequerimento(f"Data inválida em {campo}.", {campo: "inválida"})


def _bool(valor) -> bool:
    return str(valor).strip().lower() in ("1", "true", "t", "s", "sim", "on", "yes")


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )


# ---------------------------------------------------------------------------
# NUMERAÇÃO
# ---------------------------------------------------------------------------

def gerar_codigo(momento: datetime | None = None) -> tuple[str, int, str]:
    """Gera o código definitivo (REQ-000123) com lock na linha de controle."""
    momento = momento or datetime.now()
    serie = f"REQ-{momento.year}"

    # with_for_update: em MySQL/InnoDB e Postgres bloqueia a linha até o commit.
    # Em SQLite (modo desenvolvimento) o lock é ignorado, mas a escrita é serializada.
    consulta = db.session.query(ReqSequencia).filter_by(chave=serie)
    try:
        sequencia = consulta.with_for_update().first()
    except Exception:
        sequencia = consulta.first()

    if not sequencia:
        sequencia = ReqSequencia(chave=serie, ultimo_numero=0)
        db.session.add(sequencia)
        db.session.flush()

    sequencia.ultimo_numero = (sequencia.ultimo_numero or 0) + 1
    numero = sequencia.ultimo_numero
    return f"REQ-{numero:06d}", numero, serie


# ---------------------------------------------------------------------------
# HISTÓRICO / TIMELINE
# ---------------------------------------------------------------------------

def registrar_historico(requerimento: Requerimento, usuario, acao: str,
                        descricao: str | None = None,
                        status_anterior: str | None = None,
                        status_novo: str | None = None) -> ReqHistorico:
    evento = ReqHistorico(
        requerimento_id=requerimento.id,
        data_hora=datetime.now(),
        usuario_id=getattr(usuario, "id", None),
        usuario_nome=getattr(usuario, "nome", None),
        acao=acao,
        descricao=descricao,
        status_anterior=status_anterior,
        status_novo=status_novo,
    )
    db.session.add(evento)
    return evento


# ---------------------------------------------------------------------------
# CRIAÇÃO E GRAVAÇÃO
# ---------------------------------------------------------------------------

def criar_rascunho(usuario) -> Requerimento:
    """Cria o requerimento em RASCUNHO já pré-preenchido com o usuário logado."""
    requerimento = Requerimento(
        status="RASCUNHO",
        prioridade="NORMAL",
        tipo="COMPRA",
        data_referencia=date.today(),
        solicitante_usuario_id=usuario.id,
        solicitante_nome=getattr(usuario, "nome", None),
        solicitante_email=getattr(usuario, "email", None),
        solicitante_telefone=getattr(usuario, "telefone", None),
        funcionario=getattr(usuario, "nome", None),
        etapa_atual=1,
        criado_por=getattr(usuario, "nome", None),
        atualizado_por=getattr(usuario, "nome", None),
        responsavel_atual=getattr(usuario, "nome", None),
    )
    vinculos = getattr(usuario, "usu_rod", None) or []
    if vinculos:
        requerimento.responsavel = str(vinculos[0].resp).strip().upper()

    db.session.add(requerimento)
    db.session.flush()
    registrar_historico(requerimento, usuario, "CRIADO",
                        "Requerimento criado como rascunho.", None, "RASCUNHO")
    db.session.commit()
    return requerimento


def salvar(requerimento: Requerimento, payload: dict, usuario,
           validacao_completa: bool = False) -> Requerimento:
    """Grava o requerimento inteiro (cabeçalho + filhos) em uma única transação.

    `validacao_completa=False` (rascunho) valida só consistência de formato.
    `validacao_completa=True` aplica as regras obrigatórias de envio.
    """
    exigir_edicao(requerimento, usuario)

    try:
        _aplicar_geral(requerimento, payload.get("geral") or {})
        _aplicar_itens(requerimento, payload.get("itens") or [])
        _aplicar_localizacoes(requerimento, payload.get("localizacoes") or [])
        _aplicar_complementos(requerimento, payload.get("complementos") or [])
        _aplicar_cotacoes(requerimento, payload.get("cotacoes") or [])

        etapa = payload.get("etapa_atual")
        if etapa:
            try:
                requerimento.etapa_atual = max(1, min(len(ETAPAS), int(etapa)))
            except (TypeError, ValueError):
                pass

        requerimento.valor_estimado = calcular_valor_estimado(requerimento)
        requerimento.atualizado_por = getattr(usuario, "nome", None)
        requerimento.atualizado_em = datetime.now()

        erros = validar(requerimento, completo=validacao_completa)
        if erros:
            db.session.rollback()
            raise ErroRequerimento("Existem campos pendentes ou inválidos.", erros)

        db.session.commit()
    except ErroRequerimento:
        raise
    except Exception as erro:
        db.session.rollback()
        raise ErroRequerimento(f"Não foi possível salvar o requerimento: {erro}")

    return requerimento


def _aplicar_geral(requerimento: Requerimento, geral: dict) -> None:
    requerimento.tipo = _txt(geral.get("tipo"), 30) or requerimento.tipo
    if requerimento.tipo and requerimento.tipo not in TIPOS_REQUERIMENTO:
        raise ErroRequerimento("Tipo de requerimento inválido.", {"tipo": "inválido"})

    prioridade = (_txt(geral.get("prioridade"), 20) or requerimento.prioridade or "NORMAL").upper()
    if prioridade not in PRIORIDADES:
        raise ErroRequerimento("Prioridade inválida.", {"prioridade": "inválida"})
    requerimento.prioridade = prioridade

    requerimento.data_referencia = _data(geral.get("data_referencia"), "data de referência") \
        or requerimento.data_referencia
    requerimento.data_limite = _data(geral.get("data_limite"), "data limite de entrega")

    requerimento.funcionario = _txt(geral.get("funcionario"), 120)
    requerimento.solicitante_nome = _txt(geral.get("solicitante_nome"), 120) or requerimento.solicitante_nome
    requerimento.solicitante_email = _txt(geral.get("solicitante_email"), 120)
    requerimento.solicitante_telefone = _txt(geral.get("solicitante_telefone"), 30)
    requerimento.filial = _txt(geral.get("filial"), 80)
    requerimento.setor = _txt(geral.get("setor"), 80)
    requerimento.responsavel = _txt(geral.get("responsavel"), 120)

    requerimento.unidade_negocio = _txt(geral.get("unidade_negocio"), 80)
    requerimento.centro_gasto = _txt(geral.get("centro_gasto"), 80)
    requerimento.centro_custo = _txt(geral.get("centro_custo"), 80)
    requerimento.classe_sintetica = _txt(geral.get("classe_sintetica"), 80)
    requerimento.classe_analitica = _txt(geral.get("classe_analitica"), 80)
    requerimento.tipo_requisicao = _txt(geral.get("tipo_requisicao"), 80)
    requerimento.categoria = _txt(geral.get("categoria"), 80)

    requerimento.justificativa = _txt(geral.get("justificativa"))
    requerimento.observacao = _txt(geral.get("observacao"))
    requerimento.necessita_cotacao = _bool(geral.get("necessita_cotacao"))


def _aplicar_itens(requerimento: Requerimento, itens: list) -> None:
    requerimento.itens.clear()
    db.session.flush()

    vistos = set()
    for indice, bruto in enumerate(itens, start=1):
        descricao = _txt(bruto.get("produto_descricao"), 200)
        if not descricao:
            raise ErroRequerimento(f"Item {indice}: descrição do produto é obrigatória.",
                                   {f"item_{indice}_produto_descricao": "obrigatório"})

        quantidade = _dec(bruto.get("quantidade"), f"a quantidade do item {indice}", obrigatorio=True)
        if quantidade <= 0:
            raise ErroRequerimento(f"Item {indice}: a quantidade deve ser maior que zero.",
                                   {f"item_{indice}_quantidade": "deve ser > 0"})

        codigo = _txt(bruto.get("produto_codigo"), 40)
        chave = (codigo or _sem_acento(descricao).upper())
        if chave in vistos:
            raise ErroRequerimento(
                f"Item {indice}: produto duplicado no requerimento ({codigo or descricao}). "
                "Some as quantidades em um único item.",
                {f"item_{indice}_produto_codigo": "duplicado"},
            )
        vistos.add(chave)

        item = ReqItem(
            sequencia=indice,
            produto_codigo=codigo,
            produto_descricao=descricao,
            descricao_complementar=_txt(bruto.get("descricao_complementar")),
            quantidade=quantidade,
            unidade=(_txt(bruto.get("unidade"), 10) or "UN").upper(),
            data_necessidade=_data(bruto.get("data_necessidade"), f"a data de necessidade do item {indice}"),
            valor_referencia=_dec(bruto.get("valor_referencia"), f"o valor de referência do item {indice}"),
            observacao=_txt(bruto.get("observacao")),
        )
        if item.valor_referencia is not None and item.valor_referencia < 0:
            raise ErroRequerimento(f"Item {indice}: valor de referência não pode ser negativo.",
                                   {f"item_{indice}_valor_referencia": "inválido"})
        requerimento.itens.append(item)


def _aplicar_localizacoes(requerimento: Requerimento, localizacoes: list) -> None:
    sequencias = {item.sequencia for item in requerimento.itens}
    requerimento.localizacoes.clear()
    db.session.flush()

    for indice, bruto in enumerate(localizacoes, start=1):
        item_seq = bruto.get("item_sequencia")
        item_seq = int(item_seq) if str(item_seq or "").strip().isdigit() else None
        if item_seq is not None and item_seq not in sequencias:
            raise ErroRequerimento(
                f"Localização {indice}: o item informado não existe no requerimento.",
                {f"localizacao_{indice}_item": "inválido"},
            )
        campos = {
            "filial": _txt(bruto.get("filial"), 80),
            "local": _txt(bruto.get("local"), 120),
            "almoxarifado": _txt(bruto.get("almoxarifado"), 120),
            "setor": _txt(bruto.get("setor"), 80),
            "departamento": _txt(bruto.get("departamento"), 80),
            "endereco": _txt(bruto.get("endereco"), 200),
            "centro_custo": _txt(bruto.get("centro_custo"), 80),
            "responsavel_recebimento": _txt(bruto.get("responsavel_recebimento"), 120),
            "observacao": _txt(bruto.get("observacao")),
        }
        if not any(campos.values()):
            continue
        requerimento.localizacoes.append(ReqLocalizacao(item_sequencia=item_seq, **campos))


def _aplicar_complementos(requerimento: Requerimento, complementos: list) -> None:
    sequencias = {item.sequencia for item in requerimento.itens}
    requerimento.complementos.clear()
    db.session.flush()

    for indice, bruto in enumerate(complementos, start=1):
        tipo = _txt(bruto.get("tipo_movimento"), 30)
        if tipo and tipo not in TIPOS_MOVIMENTO:
            raise ErroRequerimento(f"Complemento {indice}: tipo de movimento inválido.",
                                   {f"complemento_{indice}_tipo": "inválido"})
        item_seq = bruto.get("item_sequencia")
        item_seq = int(item_seq) if str(item_seq or "").strip().isdigit() else None
        if item_seq is not None and item_seq not in sequencias:
            raise ErroRequerimento(f"Complemento {indice}: item inexistente.",
                                   {f"complemento_{indice}_item": "inválido"})

        quantidade = _dec(bruto.get("quantidade"), f"a quantidade do complemento {indice}")
        if quantidade is not None and quantidade < 0:
            raise ErroRequerimento(f"Complemento {indice}: quantidade não pode ser negativa.",
                                   {f"complemento_{indice}_quantidade": "inválida"})

        registro = ReqComplemento(
            item_sequencia=item_seq,
            tipo_movimento=tipo,
            documento_origem=_txt(bruto.get("documento_origem"), 60),
            quantidade=quantidade,
            data_movimento=_data(bruto.get("data_movimento"), f"a data do complemento {indice}"),
            almoxarifado=_txt(bruto.get("almoxarifado"), 120),
            confirmado=_bool(bruto.get("confirmado")),
            observacao=_txt(bruto.get("observacao")),
        )
        if not any([registro.tipo_movimento, registro.documento_origem, registro.quantidade,
                    registro.almoxarifado, registro.observacao]):
            continue
        requerimento.complementos.append(registro)


def _aplicar_cotacoes(requerimento: Requerimento, cotacoes: list) -> None:
    sequencias = {item.sequencia for item in requerimento.itens}
    requerimento.cotacoes.clear()
    db.session.flush()

    selecionado_indice = None
    novas = []
    for indice, bruto in enumerate(cotacoes, start=1):
        fornecedor = _txt(bruto.get("fornecedor"), 150)
        if not fornecedor:
            raise ErroRequerimento(f"Cotação {indice}: informe o fornecedor.",
                                   {f"cotacao_{indice}_fornecedor": "obrigatório"})

        item_seq = bruto.get("item_sequencia")
        item_seq = int(item_seq) if str(item_seq or "").strip().isdigit() else None
        if item_seq is not None and item_seq not in sequencias:
            raise ErroRequerimento(f"Cotação {indice}: item inexistente.",
                                   {f"cotacao_{indice}_item": "inválido"})

        quantidade = _dec(bruto.get("quantidade"), f"a quantidade da cotação {indice}", obrigatorio=True)
        preco = _dec(bruto.get("preco_unitario"), f"o preço unitário da cotação {indice}", obrigatorio=True)
        if quantidade <= 0:
            raise ErroRequerimento(f"Cotação {indice}: quantidade deve ser maior que zero.",
                                   {f"cotacao_{indice}_quantidade": "deve ser > 0"})
        if preco < 0:
            raise ErroRequerimento(f"Cotação {indice}: preço unitário inválido.",
                                   {f"cotacao_{indice}_preco_unitario": "inválido"})

        prazo = bruto.get("prazo_entrega_dias")
        prazo = int(prazo) if str(prazo or "").strip().isdigit() else None

        cotacao = ReqCotacao(
            item_sequencia=item_seq,
            fornecedor=fornecedor,
            fornecedor_documento=_txt(bruto.get("fornecedor_documento"), 20),
            produto=_txt(bruto.get("produto"), 200),
            quantidade=quantidade,
            preco_unitario=preco,
            preco_total=(quantidade * preco).quantize(Decimal("0.01")),
            prazo_entrega_dias=prazo,
            validade=_data(bruto.get("validade"), f"a validade da cotação {indice}"),
            condicao_pagamento=_txt(bruto.get("condicao_pagamento"), 80),
            observacao=_txt(bruto.get("observacao")),
            selecionada=False,
        )
        novas.append(cotacao)
        if _bool(bruto.get("selecionada")):
            # regra: no máximo um fornecedor selecionado; a seleção é sempre manual
            if selecionado_indice is not None:
                raise ErroRequerimento("Selecione apenas um fornecedor vencedor.",
                                       {"cotacoes": "mais de um selecionado"})
            selecionado_indice = indice - 1

    for cotacao in novas:
        requerimento.cotacoes.append(cotacao)
    db.session.flush()

    requerimento.cotacao_selecionada_id = None
    if selecionado_indice is not None:
        escolhida = novas[selecionado_indice]
        escolhida.selecionada = True
        requerimento.cotacao_selecionada_id = escolhida.id


# ---------------------------------------------------------------------------
# CÁLCULOS
# ---------------------------------------------------------------------------

def calcular_valor_estimado(requerimento: Requerimento) -> Decimal:
    """Valor estimado = cotação selecionada > menor cotação por item > valor de referência."""
    selecionadas = [c for c in requerimento.cotacoes if c.selecionada]
    if selecionadas:
        return sum((Decimal(c.preco_total) for c in selecionadas), Decimal("0")).quantize(Decimal("0.01"))

    if requerimento.cotacoes:
        por_item: dict = {}
        for cotacao in requerimento.cotacoes:
            chave = cotacao.item_sequencia or 0
            atual = por_item.get(chave)
            if atual is None or Decimal(cotacao.preco_total) < Decimal(atual.preco_total):
                por_item[chave] = cotacao
        return sum((Decimal(c.preco_total) for c in por_item.values()), Decimal("0")).quantize(Decimal("0.01"))

    total = sum((item.valor_total_referencia for item in requerimento.itens), Decimal("0"))
    return Decimal(total).quantize(Decimal("0.01"))


def comparativo_cotacoes(requerimento: Requerimento) -> dict:
    """Destaques do comparativo: menor preço e melhor prazo (sem escolher sozinho)."""
    if not requerimento.cotacoes:
        return {"menor_preco_id": None, "melhor_prazo_id": None}

    menor = min(requerimento.cotacoes, key=lambda c: Decimal(c.preco_total))
    com_prazo = [c for c in requerimento.cotacoes if c.prazo_entrega_dias is not None]
    melhor_prazo = min(com_prazo, key=lambda c: c.prazo_entrega_dias) if com_prazo else None
    return {
        "menor_preco_id": menor.id,
        "melhor_prazo_id": melhor_prazo.id if melhor_prazo else None,
    }


# ---------------------------------------------------------------------------
# VALIDAÇÃO
# ---------------------------------------------------------------------------

def validar(requerimento: Requerimento, completo: bool = True) -> dict:
    """Retorna {campo: mensagem}. Vazio = válido. Espelha a validação do frontend."""
    erros: dict = {}

    if requerimento.solicitante_email and not EMAIL_RE.match(requerimento.solicitante_email):
        erros["solicitante_email"] = "E-mail inválido."

    if requerimento.data_referencia and requerimento.data_limite \
            and requerimento.data_limite < requerimento.data_referencia:
        erros["data_limite"] = "A data limite não pode ser anterior à data de referência."

    if not completo:
        return erros

    obrigatorios = {
        "tipo": "Selecione o tipo do requerimento.",
        "solicitante_nome": "Informe o solicitante.",
        "solicitante_email": "Informe o e-mail do solicitante.",
        "filial": "Informe a filial.",
        "setor": "Informe o setor.",
        "centro_custo": "Informe o centro de custo.",
        "data_limite": "Informe a data limite de entrega.",
    }
    for campo, mensagem in obrigatorios.items():
        if not getattr(requerimento, campo, None):
            erros[campo] = mensagem

    justificativa = (requerimento.justificativa or "").strip()
    if len(justificativa) < 10:
        erros["justificativa"] = "Descreva a justificativa com pelo menos 10 caracteres."

    if not requerimento.itens:
        erros["itens"] = "Adicione pelo menos um item ao requerimento."

    for item in requerimento.itens:
        if Decimal(item.quantidade) <= 0:
            erros[f"item_{item.sequencia}_quantidade"] = "Quantidade deve ser maior que zero."
        if item.data_necessidade and requerimento.data_referencia \
                and item.data_necessidade < requerimento.data_referencia:
            erros[f"item_{item.sequencia}_data_necessidade"] = \
                "Data de necessidade anterior à data de referência."

    if not requerimento.localizacoes:
        erros["localizacoes"] = "Informe pelo menos um local de entrega/utilização."

    if requerimento.necessita_cotacao and not requerimento.cotacoes:
        erros["cotacoes"] = "O requerimento foi marcado como 'necessita cotação': inclua ao menos uma."

    return erros


def etapas_pendentes(requerimento: Requerimento) -> dict:
    """Situação de cada etapa (usado no stepper e no retorno ao rascunho)."""
    erros = validar(requerimento, completo=True)
    mapa = {
        "geral": ["tipo", "solicitante_nome", "solicitante_email", "filial", "setor",
                  "centro_custo", "data_limite", "justificativa", "data_referencia"],
        "itens": [chave for chave in erros if chave == "itens" or chave.startswith("item_")],
        "localizacoes": ["localizacoes"],
        "complementos": [],
        "anexos": [],
        "cotacoes": ["cotacoes"],
        "revisao": [],
    }
    situacao = {}
    for etapa in ETAPAS:
        chaves = mapa.get(etapa["slug"], [])
        pendencias = [erros[c] for c in chaves if c in erros]
        situacao[etapa["slug"]] = {
            "ok": not pendencias,
            "pendencias": pendencias,
        }
    situacao["_erros"] = erros
    return situacao


def primeira_etapa_incompleta(requerimento: Requerimento) -> int:
    situacao = etapas_pendentes(requerimento)
    for etapa in ETAPAS:
        if not situacao[etapa["slug"]]["ok"]:
            return etapa["n"]
    return requerimento.etapa_atual or len(ETAPAS)


# ---------------------------------------------------------------------------
# ENVIO / WORKFLOW / CANCELAMENTO
# ---------------------------------------------------------------------------

def enviar(requerimento: Requerimento, usuario) -> Requerimento:
    exigir_edicao(requerimento, usuario)

    requerimento.valor_estimado = calcular_valor_estimado(requerimento)
    erros = validar(requerimento, completo=True)
    if erros:
        raise ErroRequerimento("Não é possível enviar: existem pendências no requerimento.", erros)

    try:
        if not requerimento.codigo:
            codigo, numero, serie = gerar_codigo()
            requerimento.codigo = codigo
            requerimento.numero = numero
            requerimento.serie = serie

        anterior = requerimento.status
        requerimento.status = "ENVIADO"
        requerimento.enviado_em = datetime.now()
        requerimento.etapa_atual = len(ETAPAS)
        requerimento.atualizado_por = getattr(usuario, "nome", None)
        requerimento.responsavel_atual = "ATENDIMENTO"

        registrar_historico(requerimento, usuario, "ENVIADO",
                            "Requerimento enviado para análise.", anterior, "ENVIADO")
        db.session.commit()
    except ErroRequerimento:
        db.session.rollback()
        raise
    except Exception as erro:
        db.session.rollback()
        raise ErroRequerimento(f"Falha ao enviar o requerimento: {erro}")

    return requerimento


def alterar_status(requerimento: Requerimento, novo_status: str, usuario,
                   observacao: str | None = None) -> Requerimento:
    if not pode_alterar_status(usuario):
        raise AcessoNegado("Somente atendentes e administradores alteram o status.")
    if novo_status not in STATUS:
        raise ErroRequerimento("Status inválido.")

    permitidos = TRANSICOES.get(requerimento.status, [])
    if novo_status not in permitidos:
        atual = STATUS[requerimento.status]["label"]
        destino = STATUS[novo_status]["label"]
        raise ErroRequerimento(f"Transição não permitida: {atual} → {destino}.")

    try:
        anterior = requerimento.status
        requerimento.status = novo_status
        requerimento.atualizado_por = getattr(usuario, "nome", None)
        if novo_status == "CANCELADO":
            requerimento.cancelado_em = datetime.now()
            requerimento.cancelado_por = getattr(usuario, "nome", None)
            requerimento.motivo_cancelamento = observacao
        registrar_historico(requerimento, usuario, f"STATUS_{novo_status}",
                            observacao or f"Status alterado para {STATUS[novo_status]['label']}.",
                            anterior, novo_status)
        db.session.commit()
    except Exception as erro:
        db.session.rollback()
        raise ErroRequerimento(f"Falha ao alterar status: {erro}")
    return requerimento


def cancelar(requerimento: Requerimento, usuario, motivo: str | None = None) -> Requerimento:
    """Cancelamento com trilha — nunca exclusão física do documento."""
    exigir_visualizacao(requerimento, usuario)
    dono = requerimento.solicitante_usuario_id == usuario.id
    if not dono and not pode_alterar_status(usuario):
        raise AcessoNegado("Sem permissão para cancelar este requerimento.")
    if requerimento.status in ("CANCELADO", "ATENDIDO"):
        raise ErroRequerimento("Este requerimento não pode mais ser cancelado.")

    try:
        anterior = requerimento.status
        requerimento.status = "CANCELADO"
        requerimento.cancelado_em = datetime.now()
        requerimento.cancelado_por = getattr(usuario, "nome", None)
        requerimento.motivo_cancelamento = _txt(motivo)
        registrar_historico(requerimento, usuario, "CANCELADO",
                            _txt(motivo) or "Requerimento cancelado.", anterior, "CANCELADO")
        db.session.commit()
    except Exception as erro:
        db.session.rollback()
        raise ErroRequerimento(f"Falha ao cancelar: {erro}")
    return requerimento


# ---------------------------------------------------------------------------
# ANEXOS
# ---------------------------------------------------------------------------

def salvar_anexo(requerimento: Requerimento, arquivo, usuario) -> ReqAnexo:
    exigir_edicao(requerimento, usuario)

    nome_original = os.path.basename(arquivo.filename or "")
    if not nome_original:
        raise ErroRequerimento("Selecione um arquivo válido.")

    extensao = nome_original.rsplit(".", 1)[-1].lower() if "." in nome_original else ""
    if extensao not in EXTENSOES_ANEXO:
        raise ErroRequerimento(
            f"Extensão .{extensao or '?'} não permitida. Aceitos: "
            + ", ".join(sorted(EXTENSOES_ANEXO)) + "."
        )

    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)
    if tamanho == 0:
        raise ErroRequerimento("Arquivo vazio.")
    if tamanho > TAMANHO_MAX_ANEXO:
        raise ErroRequerimento("Arquivo maior que o limite de 15 MB.")

    pasta = os.path.join(ANEXOS_DIR, str(requerimento.id))
    os.makedirs(pasta, exist_ok=True)
    nome_fisico = f"{uuid.uuid4().hex}.{extensao}"
    caminho = os.path.join(pasta, nome_fisico)
    arquivo.save(caminho)

    anexo = ReqAnexo(
        requerimento_id=requerimento.id,
        nome_original=nome_original[:255],
        nome_arquivo=nome_fisico,
        extensao=extensao,
        tamanho_bytes=tamanho,
        mime=getattr(arquivo, "mimetype", None),
        enviado_por=getattr(usuario, "nome", None),
    )
    try:
        db.session.add(anexo)
        registrar_historico(requerimento, usuario, "ANEXO_ADICIONADO", f"Anexo: {anexo.nome_original}")
        db.session.commit()
    except Exception as erro:
        db.session.rollback()
        if os.path.exists(caminho):
            os.remove(caminho)
        raise ErroRequerimento(f"Falha ao registrar o anexo: {erro}")
    return anexo


def remover_anexo(requerimento: Requerimento, anexo_id: int, usuario) -> None:
    exigir_edicao(requerimento, usuario)
    anexo = ReqAnexo.query.filter_by(id=anexo_id, requerimento_id=requerimento.id).first()
    if not anexo:
        raise ErroRequerimento("Anexo não encontrado.")
    caminho = caminho_anexo(requerimento.id, anexo.nome_arquivo)
    try:
        db.session.delete(anexo)
        registrar_historico(requerimento, usuario, "ANEXO_REMOVIDO", f"Anexo removido: {anexo.nome_original}")
        db.session.commit()
    except Exception as erro:
        db.session.rollback()
        raise ErroRequerimento(f"Falha ao remover o anexo: {erro}")
    if os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass


def caminho_anexo(requerimento_id: int, nome_arquivo: str) -> str:
    return os.path.join(ANEXOS_DIR, str(requerimento_id), os.path.basename(nome_arquivo))


# ---------------------------------------------------------------------------
# CONSULTAS
# ---------------------------------------------------------------------------

def escopo_base(usuario):
    consulta = Requerimento.query
    if papel_do_usuario(usuario) == "SOLICITANTE":
        consulta = consulta.filter(Requerimento.solicitante_usuario_id == usuario.id)
    return consulta


def listar(usuario, filtros: dict, pagina: int = 1, por_pagina: int = 15,
           ordenar: str = "atualizado_em", direcao: str = "desc"):
    consulta = escopo_base(usuario)

    texto = _txt(filtros.get("q"))
    if texto:
        alvo = f"%{texto.upper()}%"
        consulta = consulta.filter(or_(
            func.upper(Requerimento.codigo).like(alvo),
            func.upper(Requerimento.solicitante_nome).like(alvo),
            func.upper(Requerimento.justificativa).like(alvo),
            func.upper(Requerimento.setor).like(alvo),
            func.upper(Requerimento.filial).like(alvo),
        ))

    for campo in ("status", "tipo", "prioridade", "filial", "setor"):
        valor = _txt(filtros.get(campo))
        if valor:
            consulta = consulta.filter(getattr(Requerimento, campo) == valor)

    solicitante = _txt(filtros.get("solicitante"))
    if solicitante:
        consulta = consulta.filter(
            func.upper(Requerimento.solicitante_nome).like(f"%{solicitante.upper()}%")
        )

    inicio = _data(filtros.get("data_inicio"), "data inicial")
    fim = _data(filtros.get("data_fim"), "data final")
    if inicio:
        consulta = consulta.filter(Requerimento.data_referencia >= inicio)
    if fim:
        consulta = consulta.filter(Requerimento.data_referencia <= fim)

    colunas = {
        "codigo": Requerimento.codigo,
        "data_referencia": Requerimento.data_referencia,
        "status": Requerimento.status,
        "prioridade": Requerimento.prioridade,
        "valor_estimado": Requerimento.valor_estimado,
        "solicitante_nome": Requerimento.solicitante_nome,
        "atualizado_em": Requerimento.atualizado_em,
    }
    coluna = colunas.get(ordenar, Requerimento.atualizado_em)
    consulta = consulta.order_by(coluna.desc() if direcao == "desc" else coluna.asc())

    por_pagina = max(5, min(100, int(por_pagina or 15)))
    return consulta.paginate(page=max(1, int(pagina or 1)), per_page=por_pagina, error_out=False)


def indicadores(usuario) -> dict:
    """Números do dashboard, calculados no banco (não em memória)."""
    consulta = escopo_base(usuario)
    total = consulta.count()

    por_status = dict(
        escopo_base(usuario)
        .with_entities(Requerimento.status, func.count(Requerimento.id))
        .group_by(Requerimento.status).all()
    )
    por_prioridade = dict(
        escopo_base(usuario)
        .with_entities(Requerimento.prioridade, func.count(Requerimento.id))
        .group_by(Requerimento.prioridade).all()
    )
    por_setor = (
        escopo_base(usuario)
        .with_entities(Requerimento.setor, func.count(Requerimento.id))
        .group_by(Requerimento.setor)
        .order_by(func.count(Requerimento.id).desc()).limit(8).all()
    )
    por_filial = (
        escopo_base(usuario)
        .with_entities(Requerimento.filial, func.count(Requerimento.id),
                       func.coalesce(func.sum(Requerimento.valor_estimado), 0))
        .group_by(Requerimento.filial)
        .order_by(func.count(Requerimento.id).desc()).limit(8).all()
    )
    por_categoria = (
        escopo_base(usuario)
        .with_entities(Requerimento.categoria,
                       func.coalesce(func.sum(Requerimento.valor_estimado), 0),
                       func.count(Requerimento.id))
        .group_by(Requerimento.categoria)
        .order_by(func.coalesce(func.sum(Requerimento.valor_estimado), 0).desc()).limit(8).all()
    )
    valor_total = escopo_base(usuario).with_entities(
        func.coalesce(func.sum(Requerimento.valor_estimado), 0)
    ).scalar() or 0

    # série por mês (usa data_referencia; agrupamento feito em Python para
    # manter compatibilidade entre MySQL e SQLite de desenvolvimento)
    linhas = escopo_base(usuario).with_entities(
        Requerimento.data_referencia, Requerimento.valor_estimado
    ).all()
    serie: dict = {}
    for data_ref, valor in linhas:
        if not data_ref:
            continue
        chave = data_ref.strftime("%Y-%m")
        registro = serie.setdefault(chave, {"periodo": chave, "quantidade": 0, "valor": 0.0})
        registro["quantidade"] += 1
        registro["valor"] += float(valor or 0)
    serie_ordenada = [serie[k] for k in sorted(serie)][-12:]

    return {
        "total": total,
        "abertos": sum(por_status.get(s, 0) for s in STATUS_ABERTOS),
        "rascunhos": por_status.get("RASCUNHO", 0),
        "por_status": [
            {"status": chave, "label": STATUS[chave]["label"], "cor": STATUS[chave]["cor"],
             "quantidade": por_status.get(chave, 0)}
            for chave in STATUS
        ],
        "por_prioridade": [
            {"prioridade": chave, "label": info["label"], "cor": info["cor"],
             "quantidade": por_prioridade.get(chave, 0)}
            for chave, info in PRIORIDADES.items()
        ],
        "por_setor": [{"setor": s or "NÃO INFORMADO", "quantidade": q} for s, q in por_setor],
        "por_filial": [{"filial": f or "NÃO INFORMADA", "quantidade": q, "valor": float(v or 0)}
                       for f, q, v in por_filial],
        "por_categoria": [{"categoria": c or "NÃO INFORMADA", "valor": float(v or 0), "quantidade": q}
                          for c, v, q in por_categoria],
        "serie_periodo": serie_ordenada,
        "valor_total": float(valor_total),
        "urgentes_abertos": escopo_base(usuario).filter(
            Requerimento.prioridade == "URGENTE",
            Requerimento.status.in_(STATUS_ABERTOS)
        ).count(),
    }


def itens_mais_solicitados(usuario, limite: int = 10) -> list:
    consulta = (
        db.session.query(
            ReqItem.produto_descricao,
            func.count(ReqItem.id),
            func.coalesce(func.sum(ReqItem.quantidade), 0),
        )
        .join(Requerimento, ReqItem.requerimento_id == Requerimento.id)
    )
    if papel_do_usuario(usuario) == "SOLICITANTE":
        consulta = consulta.filter(Requerimento.solicitante_usuario_id == usuario.id)
    linhas = (consulta.group_by(ReqItem.produto_descricao)
              .order_by(func.count(ReqItem.id).desc()).limit(limite).all())
    return [{"produto": d, "ocorrencias": o, "quantidade": float(q or 0)} for d, o, q in linhas]


def fornecedores_cotados(usuario, limite: int = 10) -> list:
    consulta = (
        db.session.query(
            ReqCotacao.fornecedor,
            func.count(ReqCotacao.id),
            func.coalesce(func.sum(ReqCotacao.preco_total), 0),
        )
        .join(Requerimento, ReqCotacao.requerimento_id == Requerimento.id)
    )
    if papel_do_usuario(usuario) == "SOLICITANTE":
        consulta = consulta.filter(Requerimento.solicitante_usuario_id == usuario.id)
    linhas = (consulta.group_by(ReqCotacao.fornecedor)
              .order_by(func.count(ReqCotacao.id).desc()).limit(limite).all())
    return [{"fornecedor": f, "cotacoes": c, "valor": float(v or 0)} for f, c, v in linhas]


def timeline_geral(usuario, limite: int = 40) -> list:
    consulta = (
        db.session.query(ReqHistorico, Requerimento)
        .join(Requerimento, ReqHistorico.requerimento_id == Requerimento.id)
    )
    if papel_do_usuario(usuario) == "SOLICITANTE":
        consulta = consulta.filter(Requerimento.solicitante_usuario_id == usuario.id)
    linhas = consulta.order_by(ReqHistorico.data_hora.desc()).limit(limite).all()
    resultado = []
    for evento, requerimento in linhas:
        registro = evento.to_dict()
        registro["requerimento_id"] = requerimento.id
        registro["requerimento_codigo"] = requerimento.codigo_exibicao
        resultado.append(registro)
    return resultado


def opcoes_filtro(usuario) -> dict:
    filiais = [f[0] for f in escopo_base(usuario).with_entities(Requerimento.filial)
               .distinct().all() if f[0]]
    setores = [s[0] for s in escopo_base(usuario).with_entities(Requerimento.setor)
               .distinct().all() if s[0]]
    return {"filiais": sorted(filiais), "setores": sorted(setores)}

"""
MÓDULO: PREVISÃO DE GASTOS

Regras de negócio para validação, importação, consolidação, anomalias e
replicação mensal.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import mean, median

from sqlalchemy import func

from core.extensoes import db
from core.previsao_models import (
    CLASSIFICACOES_INICIAIS,
    PrevisaoClassificacao,
    PrevisaoGasto,
    PrevisaoHistorico,
    PrevisaoUsuarioSetor,
)


# ============================================================
# BLOCO: NORMALIZAÇÃO E PERMISSÕES
# ============================================================

def normalizar_texto(valor):
    """Normaliza texto importado sem destruir o conteúdo apresentado ao usuário."""
    if valor is None:
        return ""
    return " ".join(str(valor).strip().split())


def usuario_pode_setor(usuario, setor: str) -> bool:
    """
    Verifica se o usuário pode operar o setor informado.

    REGRA:
    Administradores podem operar todos os setores. Usuários comuns precisam
    possuir vínculo explícito em prev_usuario_setor.
    """
    setor = normalizar_texto(setor)
    if getattr(usuario, "ADM", "N") == "S":
        return True
    if not setor or not getattr(usuario, "id", None):
        return False
    return db.session.query(PrevisaoUsuarioSetor).filter_by(
        usuario_id=usuario.id, setor=setor
    ).first() is not None


def setores_permitidos(usuario):
    """Retorna setores operáveis pelo usuário, preservando a regra de acesso."""
    if getattr(usuario, "ADM", "N") == "S":
        return [r[0] for r in db.session.query(PrevisaoGasto.setor).distinct().order_by(PrevisaoGasto.setor)]
    return [r.setor for r in db.session.query(PrevisaoUsuarioSetor).filter_by(usuario_id=usuario.id).order_by(PrevisaoUsuarioSetor.setor).all()]


# ============================================================
# BLOCO: CLASSIFICAÇÕES
# ============================================================

def garantir_classificacoes_iniciais():
    """
    Garante o catálogo inicial baseado na planilha fictícia.

    A operação é idempotente: uma classificação existente não é duplicada.
    """
    for nome in CLASSIFICACOES_INICIAIS:
        existente = PrevisaoClassificacao.query.filter(func.lower(PrevisaoClassificacao.nome) == nome.lower()).first()
        if not existente:
            db.session.add(PrevisaoClassificacao(nome=nome, ativa=True))
    db.session.commit()


def obter_classificacao(nome):
    """Busca classificação de forma case-insensitive e retorna None quando não encontrada."""
    nome = normalizar_texto(nome)
    if not nome:
        return None
    return PrevisaoClassificacao.query.filter(func.lower(PrevisaoClassificacao.nome) == nome.lower()).first()


# ============================================================
# BLOCO: VALIDAÇÃO DE LANÇAMENTOS
# ============================================================

def validar_lancamento(dados, usuario=None):
    """
    Valida um lançamento antes da persistência.

    ENTRADA:
    Dicionário normalizado contendo setor, vencimento, valor, fornecedor,
    referência e classificação.

    SAÍDA:
    {"erros": [...], "alertas": [...]}.

    REGRA:
    Erros impedem confirmação; alertas podem ser revisados pelo usuário.
    """
    erros = []
    alertas = []

    setor = normalizar_texto(dados.get("setor"))
    fornecedor = normalizar_texto(dados.get("fornecedor"))
    referencia = normalizar_texto(dados.get("referencia"))
    classificacao = normalizar_texto(dados.get("classificacao"))

    if not setor:
        erros.append("Setor não informado.")
    elif usuario is not None and not usuario_pode_setor(usuario, setor):
        erros.append(f"Usuário sem permissão para o setor '{setor}'.")

    if not fornecedor:
        alertas.append("Fornecedor não informado.")
    if not referencia:
        alertas.append("Referência do serviço/produto não informada.")
    if not classificacao:
        erros.append("Classificação não informada.")
    elif not obter_classificacao(classificacao):
        alertas.append(f"Classificação '{classificacao}' ainda não existe no catálogo.")

    valor = dados.get("valor")
    try:
        valor_decimal = Decimal(str(valor).replace(".", "").replace(",", ".")) if isinstance(valor, str) else Decimal(str(valor))
    except (InvalidOperation, ValueError):
        valor_decimal = None
        erros.append("Valor previsto inválido.")

    if valor is None or str(valor).strip() == "":
        erros.append("Valor previsto não informado.")
    elif valor_decimal is not None and valor_decimal < 0:
        erros.append("Valor previsto não pode ser negativo.")
    elif valor_decimal == 0:
        alertas.append("Valor previsto igual a zero. Informe uma justificativa se este lançamento for mantido.")

    if not dados.get("vencimento"):
        alertas.append("Vencimento não informado.")

    return {"erros": erros, "alertas": alertas}


# ============================================================
# BLOCO: ANÁLISE HISTÓRICA E ANOMALIAS
# ============================================================

def analisar_anomalia(dados):
    """
    Compara um lançamento com históricos equivalentes.

    CRITÉRIO:
    Prioriza a combinação setor + CIA + fornecedor + classificação. Quando
    houver poucos registros, amplia a referência gradualmente para setor +
    classificação e setor.

    A análise é informativa e não bloqueia a gravação.
    """
    setor = normalizar_texto(dados.get("setor"))
    cia = normalizar_texto(dados.get("cia"))
    fornecedor = normalizar_texto(dados.get("fornecedor"))
    classificacao = normalizar_texto(dados.get("classificacao"))

    try:
        valor_atual = Decimal(str(dados.get("valor")))
    except (InvalidOperation, ValueError, TypeError):
        return {"nivel": "ERRO", "mensagem": "Valor inválido.", "historico_suficiente": False}

    base = PrevisaoGasto.query.filter(PrevisaoGasto.setor == setor)
    candidatos = base.filter(PrevisaoGasto.classificacao_nome == classificacao)
    if cia:
        candidatos_cia = candidatos.filter(PrevisaoGasto.cia == cia).all()
        if len(candidatos_cia) >= 3:
            historico = candidatos_cia
        else:
            historico = candidatos.all()
    else:
        historico = candidatos.all()

    if fornecedor:
        historico_fornecedor = [h for h in historico if normalizar_texto(h.fornecedor).lower() == fornecedor.lower()]
        if len(historico_fornecedor) >= 3:
            historico = historico_fornecedor

    valores = [h.valor_decimal for h in historico if h.valor is not None and h.valor_decimal >= 0]
    if len(valores) < 3:
        return {
            "nivel": "SEM_HISTORICO",
            "mensagem": "Não há histórico suficiente para avaliar este lançamento.",
            "historico_suficiente": False,
            "quantidade": len(valores),
        }

    media = Decimal(str(mean([float(v) for v in valores])))
    mediana = Decimal(str(median([float(v) for v in valores])))
    if media == 0:
        return {
            "nivel": "ATENCAO",
            "mensagem": "Histórico possui média igual a zero; revise o lançamento.",
            "historico_suficiente": True,
            "media": float(media),
            "mediana": float(mediana),
            "variacao_percentual": None,
        }

    variacao = ((valor_atual - media) / media) * Decimal("100")
    abs_variacao = abs(variacao)

    # REGRA DE NEGÓCIO:
    # 30% é o início do alerta e 60% representa anomalia forte. Os limites são
    # critérios de apresentação, não uma proibição de lançamento.
    nivel = "NORMAL"
    if abs_variacao >= Decimal("60"):
        nivel = "ANOMALIA"
    elif abs_variacao >= Decimal("30"):
        nivel = "ATENCAO"

    return {
        "nivel": nivel,
        "mensagem": {
            "NORMAL": "Valor dentro do comportamento histórico.",
            "ATENCAO": "Valor apresenta variação relevante em relação ao histórico.",
            "ANOMALIA": "Valor apresenta variação excepcional em relação ao histórico.",
        }[nivel],
        "historico_suficiente": True,
        "quantidade": len(valores),
        "media": float(media),
        "mediana": float(mediana),
        "variacao_percentual": round(float(variacao), 2),
    }


# ============================================================
# BLOCO: CONSOLIDAÇÃO
# ============================================================

def consolidar(filtros=None):
    """
    Consolida valores por setor, CIA, fornecedor, classificação e competência.

    Filtros são aplicados antes da agregação para que o dashboard e a tela de
    consulta compartilhem a mesma regra de totalização.
    """
    filtros = filtros or {}
    query = PrevisaoGasto.query
    if filtros.get("setor"):
        query = query.filter_by(setor=filtros["setor"])
    if filtros.get("cia"):
        query = query.filter_by(cia=filtros["cia"])
    if filtros.get("fornecedor"):
        query = query.filter_by(fornecedor=filtros["fornecedor"])
    if filtros.get("classificacao"):
        query = query.filter_by(classificacao_nome=filtros["classificacao"])
    if filtros.get("competencia"):
        query = query.filter_by(competencia=filtros["competencia"])

    registros = query.order_by(PrevisaoGasto.competencia, PrevisaoGasto.id).all()
    total = sum((r.valor_decimal for r in registros), Decimal("0.00"))

    def agrupar(chave):
        resultado = {}
        for registro in registros:
            nome = getattr(registro, chave) or "Não informado"
            resultado[nome] = resultado.get(nome, Decimal("0.00")) + registro.valor_decimal
        return [{"nome": k, "valor": float(v)} for k, v in sorted(resultado.items())]

    return {
        "total": float(total),
        "quantidade": len(registros),
        "por_setor": agrupar("setor"),
        "por_cia": agrupar("cia"),
        "por_fornecedor": agrupar("fornecedor"),
        "por_classificacao": agrupar("classificacao_nome"),
        "por_mes": agrupar("competencia"),
    }


# ============================================================
# BLOCO: REPLICAÇÃO MENSAL
# ============================================================

def proximo_mes(data):
    """Calcula o mesmo dia no mês seguinte, ajustando meses menores."""
    ano = data.year + (1 if data.month == 12 else 0)
    mes = 1 if data.month == 12 else data.month + 1
    dia = min(data.day, monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def replicar(registros, nova_competencia, usuario, percentual=0):
    """
    Cria novos lançamentos para a competência de destino.

    DECISÃO:
    O registro original nunca é alterado. A replicação cria novos objetos.

    DEDUPLICIDADE:
    O usuário recebe a lista de potenciais duplicidades antes da confirmação.
    Esta função assume que a etapa de revisão já foi concluída.
    """
    novos = []
    multiplicador = Decimal("1") + (Decimal(str(percentual)) / Decimal("100"))
    for original in registros:
        if not usuario_pode_setor(usuario, original.setor):
            continue
        novo = PrevisaoGasto(
            setor=original.setor,
            competencia=nova_competencia,
            cia=original.cia,
            fornecedor=original.fornecedor,
            vencimento=original.vencimento,
            valor=(original.valor_decimal * multiplicador).quantize(Decimal("0.01")),
            referencia=original.referencia,
            classificacao_id=original.classificacao_id,
            classificacao_nome=original.classificacao_nome,
            observacao=original.observacao,
            status="EM_PREENCHIMENTO",
            criado_por=usuario.id,
            atualizado_por=usuario.id,
        )
        db.session.add(novo)
        novos.append(novo)
    db.session.commit()
    return novos


# ============================================================
# BLOCO: HISTÓRICO
# ============================================================

def registrar_historico(previsao, usuario, campo, anterior, novo, motivo=None):
    """Registra alteração de um campo para auditoria financeira."""
    evento = PrevisaoHistorico(
        previsao_id=previsao.id,
        usuario_id=usuario.id,
        campo=campo,
        valor_anterior=None if anterior is None else str(anterior),
        valor_novo=None if novo is None else str(novo),
        motivo=motivo,
    )
    db.session.add(evento)

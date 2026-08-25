# core/req_models.py
"""
Modelos do domínio REQUERIMENTO.

Referência de negócio: tela legada de Requisição de Compras do ERP
(abas Geral / Itens / Localizações / Baixas / Anexos / Cotações).

IMPORTANTE (regra 41 do escopo): nenhum campo do ERP foi inventado como se fosse
real. As tabelas abaixo são NOVAS e pertencem ao banco da aplicação web
(prefixo `req_`). Os campos que vêm do ERP (produtos, centros de custo, filiais,
classes) são consumidos via `core/req_catalogos.py`, que lê os JSON de integração
quando existirem e cai em catálogo de desenvolvimento explicitamente marcado
quando não existirem.
"""

from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)

from core.extensoes import db


# ---------------------------------------------------------------------------
# CATÁLOGOS DE DOMÍNIO (ajustáveis conforme as regras reais do ERP)
# ---------------------------------------------------------------------------

# A lista abaixo é a configuração de status da APLICAÇÃO WEB.
# Não se assume que todos existam no ERP: para adequar, basta editar este dicionário
# (chave = valor gravado no banco) e, se necessário, o mapa TRANSICOES.
STATUS = {
    "RASCUNHO":            {"label": "Rascunho",             "cor": "#64748b", "icone": "file-pen"},
    "ENVIADO":             {"label": "Enviado",              "cor": "#14B1E7", "icone": "send"},
    "EM_ANALISE":          {"label": "Em análise",           "cor": "#6366f1", "icone": "search"},
    "AGUARDANDO_APROVACAO": {"label": "Aguardando aprovação", "cor": "#f59e0b", "icone": "clock"},
    "APROVADO":            {"label": "Aprovado",             "cor": "#10b981", "icone": "check-circle"},
    "REPROVADO":           {"label": "Reprovado",            "cor": "#ef4444", "icone": "x-circle"},
    "EM_COTACAO":          {"label": "Em cotação",           "cor": "#0ea5e9", "icone": "calculator"},
    "EM_COMPRA":           {"label": "Em compra",            "cor": "#8b5cf6", "icone": "shopping-cart"},
    "ATENDIDO":            {"label": "Atendido",             "cor": "#059669", "icone": "package-check"},
    "CANCELADO":           {"label": "Cancelado",            "cor": "#64748b", "icone": "ban"},
}

# Transições permitidas (fluxo operacional). Editável conforme o ERP.
TRANSICOES = {
    "RASCUNHO":             ["ENVIADO", "CANCELADO"],
    "ENVIADO":              ["EM_ANALISE", "AGUARDANDO_APROVACAO", "CANCELADO"],
    "EM_ANALISE":           ["AGUARDANDO_APROVACAO", "EM_COTACAO", "REPROVADO", "CANCELADO"],
    "AGUARDANDO_APROVACAO": ["APROVADO", "REPROVADO", "CANCELADO"],
    "APROVADO":             ["EM_COTACAO", "EM_COMPRA", "ATENDIDO", "CANCELADO"],
    "EM_COTACAO":           ["AGUARDANDO_APROVACAO", "EM_COMPRA", "CANCELADO"],
    "EM_COMPRA":            ["ATENDIDO", "CANCELADO"],
    "ATENDIDO":             [],
    "REPROVADO":            ["RASCUNHO"],
    "CANCELADO":            [],
}

STATUS_ABERTOS = ["ENVIADO", "EM_ANALISE", "AGUARDANDO_APROVACAO", "EM_COTACAO", "EM_COMPRA"]

PRIORIDADES = {
    "BAIXA":   {"label": "Baixa",   "cor": "#94a3b8", "peso": 1},
    "NORMAL":  {"label": "Normal",  "cor": "#14B1E7", "peso": 2},
    "ALTA":    {"label": "Alta",    "cor": "#f59e0b", "peso": 3},
    "URGENTE": {"label": "Urgente", "cor": "#ef4444", "peso": 4},
}

TIPOS_REQUERIMENTO = {
    "COMPRA":       "Compra de material",
    "SERVICO":      "Contratação de serviço",
    "ALMOXARIFADO": "Requisição de almoxarifado",
    "MANUTENCAO":   "Manutenção",
    "OUTRO":        "Outro",
}

# Reinterpretação da aba "Baixas" do ERP legado.
# ATENÇÃO: a semântica exata dos campos da aba Baixas precisa ser confirmada na base
# do ERP. Aqui ela é tratada como registro de movimentação/consumo vinculada ao
# requerimento (ver docs/REQUERIMENTOS.md, seção "Baixas").
TIPOS_MOVIMENTO = {
    "CONSUMO":       "Consumo previsto",
    "BAIXA_ESTOQUE": "Baixa de estoque",
    "SUBSTITUICAO":  "Substituição de material",
    "TRANSFERENCIA": "Transferência entre locais",
    "ATENDIMENTO":   "Atendimento / entrega",
}

PAPEIS = {
    "SOLICITANTE":   "Solicitante",
    "ATENDENTE":     "Atendente",
    "ADMINISTRADOR": "Administrador",
}

ETAPAS = [
    {"n": 1, "slug": "geral",        "titulo": "Geral",         "icone": "file-plus",
     "descricao": "Identificação, solicitante e classificação do requerimento."},
    {"n": 2, "slug": "itens",        "titulo": "Itens",         "icone": "package",
     "descricao": "Produtos, serviços e quantidades solicitadas."},
    {"n": 3, "slug": "localizacoes", "titulo": "Localizações",  "icone": "map-pin",
     "descricao": "Onde os itens serão entregues ou utilizados."},
    {"n": 4, "slug": "complementos", "titulo": "Complementos",  "icone": "clipboard-list",
     "descricao": "Baixas e informações complementares do processo."},
    {"n": 5, "slug": "anexos",       "titulo": "Anexos",        "icone": "paperclip",
     "descricao": "Documentos de apoio ao requerimento."},
    {"n": 6, "slug": "cotacoes",     "titulo": "Cotações",      "icone": "calculator",
     "descricao": "Fornecedores, preços e prazos para comparação."},
    {"n": 7, "slug": "revisao",      "titulo": "Revisão",       "icone": "check-circle",
     "descricao": "Confira tudo antes de enviar."},
]

EXTENSOES_ANEXO = {"pdf", "jpg", "jpeg", "png", "xls", "xlsx", "doc", "docx"}
TAMANHO_MAX_ANEXO = 15 * 1024 * 1024  # 15 MB


# ---------------------------------------------------------------------------
# TABELAS
# ---------------------------------------------------------------------------

class ReqSequencia(db.Model):
    """Controle de numeração de documento por série/ano (nunca MAX(numero)+1 sem lock)."""

    __tablename__ = "req_sequencia"

    chave = db.Column(String(20), primary_key=True)      # ex.: "REQ-2026"
    ultimo_numero = db.Column(Integer, nullable=False, default=0)


class ReqUsuarioPapel(db.Model):
    """Papel do usuário dentro do domínio de requerimentos.

    Não altera a tabela `usuarios` existente (que só possui ADM S/N).
    Quando não há registro aqui: ADM='S' => ADMINISTRADOR, caso contrário SOLICITANTE.
    """

    __tablename__ = "req_usuario_papel"

    usuario_id = db.Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    papel = db.Column(String(20), nullable=False, default="SOLICITANTE")


class Requerimento(db.Model):
    __tablename__ = "req_requerimento"

    id = db.Column(Integer, primary_key=True)
    codigo = db.Column(String(20), unique=True, nullable=True)   # REQ-000123 (gerado no envio/salvamento)
    numero = db.Column(Integer, nullable=True)                   # sequencial dentro da série
    serie = db.Column(String(20), nullable=True)

    status = db.Column(String(30), nullable=False, default="RASCUNHO", index=True)
    tipo = db.Column(String(30), nullable=True)
    prioridade = db.Column(String(20), nullable=False, default="NORMAL")

    data_referencia = db.Column(Date, nullable=True)
    data_limite = db.Column(Date, nullable=True)

    # --- Solicitante ---
    solicitante_usuario_id = db.Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    solicitante_nome = db.Column(String(120), nullable=True)
    solicitante_email = db.Column(String(120), nullable=True)
    solicitante_telefone = db.Column(String(30), nullable=True)
    funcionario = db.Column(String(120), nullable=True)
    filial = db.Column(String(80), nullable=True)
    setor = db.Column(String(80), nullable=True)
    responsavel = db.Column(String(120), nullable=True)

    # --- Classificação ---
    unidade_negocio = db.Column(String(80), nullable=True)
    centro_gasto = db.Column(String(80), nullable=True)
    centro_custo = db.Column(String(80), nullable=True)
    classe_sintetica = db.Column(String(80), nullable=True)
    classe_analitica = db.Column(String(80), nullable=True)
    tipo_requisicao = db.Column(String(80), nullable=True)
    categoria = db.Column(String(80), nullable=True)

    justificativa = db.Column(Text, nullable=True)
    observacao = db.Column(Text, nullable=True)

    necessita_cotacao = db.Column(Boolean, nullable=False, default=False)
    cotacao_selecionada_id = db.Column(Integer, nullable=True)   # sem FK: evita ciclo entre tabelas

    etapa_atual = db.Column(Integer, nullable=False, default=1)
    valor_estimado = db.Column(Numeric(15, 2), nullable=False, default=Decimal("0.00"))
    responsavel_atual = db.Column(String(120), nullable=True)

    enviado_em = db.Column(DateTime, nullable=True)
    criado_em = db.Column(DateTime, nullable=False, default=datetime.now)
    criado_por = db.Column(String(120), nullable=True)
    atualizado_em = db.Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    atualizado_por = db.Column(String(120), nullable=True)
    cancelado_em = db.Column(DateTime, nullable=True)
    cancelado_por = db.Column(String(120), nullable=True)
    motivo_cancelamento = db.Column(Text, nullable=True)

    itens = db.relationship("ReqItem", backref="requerimento", cascade="all, delete-orphan",
                            order_by="ReqItem.sequencia", lazy="selectin")
    localizacoes = db.relationship("ReqLocalizacao", backref="requerimento",
                                   cascade="all, delete-orphan", lazy="selectin")
    complementos = db.relationship("ReqComplemento", backref="requerimento",
                                   cascade="all, delete-orphan", lazy="selectin")
    anexos = db.relationship("ReqAnexo", backref="requerimento",
                             cascade="all, delete-orphan", lazy="selectin")
    cotacoes = db.relationship("ReqCotacao", backref="requerimento",
                               cascade="all, delete-orphan", lazy="selectin")
    historico = db.relationship("ReqHistorico", backref="requerimento", cascade="all, delete-orphan",
                                order_by="ReqHistorico.data_hora", lazy="selectin")

    __table_args__ = (
        Index("ix_req_status_prioridade", "status", "prioridade"),
    )

    # -- helpers de apresentação ------------------------------------------------
    @property
    def codigo_exibicao(self) -> str:
        if self.codigo:
            return self.codigo
        return f"RASCUNHO Nº {self.id}" if self.id else "NOVO RASCUNHO"

    @property
    def status_info(self) -> dict:
        return STATUS.get(self.status, {"label": self.status, "cor": "#94a3b8", "icone": "circle"})

    @property
    def prioridade_info(self) -> dict:
        return PRIORIDADES.get(self.prioridade, PRIORIDADES["NORMAL"])

    @property
    def editavel(self) -> bool:
        return self.status == "RASCUNHO"

    def to_dict(self, completo: bool = False) -> dict:
        base = {
            "id": self.id,
            "codigo": self.codigo,
            "codigo_exibicao": self.codigo_exibicao,
            "status": self.status,
            "status_label": self.status_info["label"],
            "status_cor": self.status_info["cor"],
            "tipo": self.tipo,
            "tipo_label": TIPOS_REQUERIMENTO.get(self.tipo, self.tipo or ""),
            "prioridade": self.prioridade,
            "prioridade_label": self.prioridade_info["label"],
            "data_referencia": _iso(self.data_referencia),
            "data_limite": _iso(self.data_limite),
            "solicitante_nome": self.solicitante_nome,
            "solicitante_email": self.solicitante_email,
            "solicitante_telefone": self.solicitante_telefone,
            "funcionario": self.funcionario,
            "filial": self.filial,
            "setor": self.setor,
            "responsavel": self.responsavel,
            "unidade_negocio": self.unidade_negocio,
            "centro_gasto": self.centro_gasto,
            "centro_custo": self.centro_custo,
            "classe_sintetica": self.classe_sintetica,
            "classe_analitica": self.classe_analitica,
            "tipo_requisicao": self.tipo_requisicao,
            "categoria": self.categoria,
            "justificativa": self.justificativa,
            "observacao": self.observacao,
            "necessita_cotacao": bool(self.necessita_cotacao),
            "cotacao_selecionada_id": self.cotacao_selecionada_id,
            "etapa_atual": self.etapa_atual,
            "valor_estimado": _num(self.valor_estimado),
            "responsavel_atual": self.responsavel_atual,
            "qtd_itens": len(self.itens),
            "qtd_anexos": len(self.anexos),
            "editavel": self.editavel,
            "enviado_em": _iso(self.enviado_em),
            "criado_em": _iso(self.criado_em),
            "atualizado_em": _iso(self.atualizado_em),
        }
        if completo:
            base.update({
                "itens": [i.to_dict() for i in self.itens],
                "localizacoes": [l.to_dict() for l in self.localizacoes],
                "complementos": [c.to_dict() for c in self.complementos],
                "anexos": [a.to_dict() for a in self.anexos],
                "cotacoes": [c.to_dict() for c in self.cotacoes],
                "historico": [h.to_dict() for h in self.historico],
            })
        return base


class ReqItem(db.Model):
    __tablename__ = "req_item"

    id = db.Column(Integer, primary_key=True)
    requerimento_id = db.Column(Integer, ForeignKey("req_requerimento.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    sequencia = db.Column(Integer, nullable=False, default=1)
    produto_codigo = db.Column(String(40), nullable=True)
    produto_descricao = db.Column(String(200), nullable=False)
    descricao_complementar = db.Column(Text, nullable=True)
    quantidade = db.Column(Numeric(15, 4), nullable=False, default=Decimal("1"))
    unidade = db.Column(String(10), nullable=False, default="UN")
    data_necessidade = db.Column(Date, nullable=True)
    valor_referencia = db.Column(Numeric(15, 4), nullable=True)
    observacao = db.Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("requerimento_id", "sequencia", name="uq_req_item_seq"),
    )

    @property
    def valor_total_referencia(self) -> Decimal:
        if self.valor_referencia is None:
            return Decimal("0")
        return (Decimal(self.quantidade) * Decimal(self.valor_referencia)).quantize(Decimal("0.01"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sequencia": self.sequencia,
            "produto_codigo": self.produto_codigo,
            "produto_descricao": self.produto_descricao,
            "descricao_complementar": self.descricao_complementar,
            "quantidade": _num(self.quantidade),
            "unidade": self.unidade,
            "data_necessidade": _iso(self.data_necessidade),
            "valor_referencia": _num(self.valor_referencia),
            "valor_total_referencia": _num(self.valor_total_referencia),
            "observacao": self.observacao,
        }


class ReqLocalizacao(db.Model):
    __tablename__ = "req_localizacao"

    id = db.Column(Integer, primary_key=True)
    requerimento_id = db.Column(Integer, ForeignKey("req_requerimento.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    item_sequencia = db.Column(Integer, nullable=True)   # null = vale para todo o requerimento
    filial = db.Column(String(80), nullable=True)
    local = db.Column(String(120), nullable=True)
    almoxarifado = db.Column(String(120), nullable=True)
    setor = db.Column(String(80), nullable=True)
    departamento = db.Column(String(80), nullable=True)
    endereco = db.Column(String(200), nullable=True)
    centro_custo = db.Column(String(80), nullable=True)
    responsavel_recebimento = db.Column(String(120), nullable=True)
    observacao = db.Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_sequencia": self.item_sequencia,
            "filial": self.filial,
            "local": self.local,
            "almoxarifado": self.almoxarifado,
            "setor": self.setor,
            "departamento": self.departamento,
            "endereco": self.endereco,
            "centro_custo": self.centro_custo,
            "responsavel_recebimento": self.responsavel_recebimento,
            "observacao": self.observacao,
        }


class ReqComplemento(db.Model):
    """Aba "Baixas" do ERP reinterpretada: movimentações/informações complementares."""

    __tablename__ = "req_complemento"

    id = db.Column(Integer, primary_key=True)
    requerimento_id = db.Column(Integer, ForeignKey("req_requerimento.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    item_sequencia = db.Column(Integer, nullable=True)
    tipo_movimento = db.Column(String(30), nullable=True)
    documento_origem = db.Column(String(60), nullable=True)
    quantidade = db.Column(Numeric(15, 4), nullable=True)
    data_movimento = db.Column(Date, nullable=True)
    almoxarifado = db.Column(String(120), nullable=True)
    confirmado = db.Column(Boolean, nullable=False, default=False)
    observacao = db.Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_sequencia": self.item_sequencia,
            "tipo_movimento": self.tipo_movimento,
            "tipo_movimento_label": TIPOS_MOVIMENTO.get(self.tipo_movimento, self.tipo_movimento or ""),
            "documento_origem": self.documento_origem,
            "quantidade": _num(self.quantidade),
            "data_movimento": _iso(self.data_movimento),
            "almoxarifado": self.almoxarifado,
            "confirmado": bool(self.confirmado),
            "observacao": self.observacao,
        }


class ReqAnexo(db.Model):
    __tablename__ = "req_anexo"

    id = db.Column(Integer, primary_key=True)
    requerimento_id = db.Column(Integer, ForeignKey("req_requerimento.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    nome_original = db.Column(String(255), nullable=False)
    nome_arquivo = db.Column(String(255), nullable=False)   # nome físico (uuid.ext) em storage/anexos
    extensao = db.Column(String(10), nullable=True)
    tamanho_bytes = db.Column(Integer, nullable=False, default=0)
    mime = db.Column(String(120), nullable=True)
    enviado_em = db.Column(DateTime, nullable=False, default=datetime.now)
    enviado_por = db.Column(String(120), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome_original": self.nome_original,
            "extensao": self.extensao,
            "tamanho_bytes": self.tamanho_bytes,
            "tamanho_legivel": tamanho_legivel(self.tamanho_bytes),
            "enviado_em": _iso(self.enviado_em),
            "enviado_por": self.enviado_por,
        }


class ReqCotacao(db.Model):
    __tablename__ = "req_cotacao"

    id = db.Column(Integer, primary_key=True)
    requerimento_id = db.Column(Integer, ForeignKey("req_requerimento.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    item_sequencia = db.Column(Integer, nullable=True)
    fornecedor = db.Column(String(150), nullable=False)
    fornecedor_documento = db.Column(String(20), nullable=True)
    produto = db.Column(String(200), nullable=True)
    quantidade = db.Column(Numeric(15, 4), nullable=False, default=Decimal("1"))
    preco_unitario = db.Column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    preco_total = db.Column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    prazo_entrega_dias = db.Column(Integer, nullable=True)
    validade = db.Column(Date, nullable=True)
    condicao_pagamento = db.Column(String(80), nullable=True)
    observacao = db.Column(Text, nullable=True)
    selecionada = db.Column(Boolean, nullable=False, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_sequencia": self.item_sequencia,
            "fornecedor": self.fornecedor,
            "fornecedor_documento": self.fornecedor_documento,
            "produto": self.produto,
            "quantidade": _num(self.quantidade),
            "preco_unitario": _num(self.preco_unitario),
            "preco_total": _num(self.preco_total),
            "prazo_entrega_dias": self.prazo_entrega_dias,
            "validade": _iso(self.validade),
            "condicao_pagamento": self.condicao_pagamento,
            "observacao": self.observacao,
            "selecionada": bool(self.selecionada),
        }


class ReqHistorico(db.Model):
    __tablename__ = "req_historico"

    id = db.Column(Integer, primary_key=True)
    requerimento_id = db.Column(Integer, ForeignKey("req_requerimento.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    data_hora = db.Column(DateTime, nullable=False, default=datetime.now)
    usuario_id = db.Column(Integer, nullable=True)
    usuario_nome = db.Column(String(120), nullable=True)
    acao = db.Column(String(60), nullable=False)
    status_anterior = db.Column(String(30), nullable=True)
    status_novo = db.Column(String(30), nullable=True)
    descricao = db.Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "data_hora": _iso(self.data_hora),
            "data_hora_br": self.data_hora.strftime("%d/%m/%Y %H:%M") if self.data_hora else "",
            "usuario_nome": self.usuario_nome,
            "acao": self.acao,
            "status_anterior": self.status_anterior,
            "status_novo": self.status_novo,
            "status_novo_label": STATUS.get(self.status_novo, {}).get("label", self.status_novo or ""),
            "descricao": self.descricao,
        }


# ---------------------------------------------------------------------------
# utilitários locais
# ---------------------------------------------------------------------------

def _iso(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return None


def _num(valor):
    if valor is None:
        return None
    return float(Decimal(valor))


def tamanho_legivel(bytes_: int) -> str:
    tamanho = float(bytes_ or 0)
    for unidade in ("B", "KB", "MB", "GB"):
        if tamanho < 1024 or unidade == "GB":
            if unidade == "B":
                return f"{int(tamanho)} {unidade}"
            return f"{tamanho:.1f} {unidade}".replace(".", ",")
        tamanho /= 1024
    return f"{tamanho:.1f} GB"

"""
MÓDULO: PREVISÃO DE GASTOS

Entidades novas do módulo de planejamento orçamentário.

REGRA DE INTEGRAÇÃO:
- Não duplica a tabela `usuarios`.
- O setor é reutilizado do domínio de requerimentos quando já existir.
- A tabela de vínculo de usuário/setor é somente uma camada de permissão do
  módulo, não um novo cadastro mestre de setores.
- Os lançamentos importados da planilha são persistidos somente após revisão.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Index

from core.extensoes import db


# ============================================================
# MÓDULO: PREVISÃO DE GASTOS
# BLOCO: CLASSIFICAÇÕES
# ============================================================
# Catálogo inicial baseado na planilha fictícia fornecida.
# A tabela permite adicionar novas classificações sem alterar o modelo.
CLASSIFICACOES_INICIAIS = [
    "FORNECEDORES ESTRANGEIROS",
    "FORNECEDORES",
    "IMPOSTOS",
    "FOLHA",
    "RESCISÃO (INCLUSIVE DIRETORES)",
    "ENCARGOS E BENEFÍCIOS",
    "DESPESAS COMERCIAIS",
    "BALSAS",
    "DESPESAS OPERACIONAIS (GGF + ADM)",
    "COMPRA DE ATIVO",
]


class PrevisaoClassificacao(db.Model):
    """
    Catálogo de classificação dos pagamentos previstos.

    RELACIONAMENTO:
    Um lançamento de previsão utiliza uma classificação ativa.

    IMPORTANTE:
    As classificações iniciais vêm do modelo fictício, mas o usuário
    administrativo poderá acrescentar outras no futuro.
    """

    __tablename__ = "prev_classificacao"

    id = db.Column(Integer, primary_key=True)
    nome = db.Column(String(120), nullable=False, unique=True, index=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criada_em = db.Column(DateTime, nullable=False, default=datetime.now)
    atualizada_em = db.Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class PrevisaoUsuarioSetor(db.Model):
    """
    Permissão de usuário por setor dentro do módulo de previsão.

    DECISÃO:
    Esta tabela não representa um novo cadastro de setores. Ela apenas
    registra quais setores um usuário pode operar quando não for administrador.
    """

    __tablename__ = "prev_usuario_setor"

    usuario_id = db.Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    setor = db.Column(String(120), primary_key=True)


class PrevisaoGasto(db.Model):
    """
    Lançamento individual de previsão de gasto.

    CAMPOS DE NEGÓCIO:
    setor, competência, CIA, fornecedor, vencimento, valor, referência e
    classificação reproduzem a lógica da planilha, com informações adicionais
    para rastreabilidade e controle da aplicação.
    """

    __tablename__ = "prev_gasto"

    id = db.Column(Integer, primary_key=True)
    setor = db.Column(String(120), nullable=False, index=True)
    competencia = db.Column(Date, nullable=False, index=True)
    cia = db.Column(String(80), nullable=True, index=True)
    fornecedor = db.Column(String(180), nullable=True, index=True)
    vencimento = db.Column(Date, nullable=True, index=True)
    valor = db.Column(Numeric(15, 2), nullable=False, default=Decimal("0.00"))
    referencia = db.Column(Text, nullable=True)
    classificacao_id = db.Column(Integer, ForeignKey("prev_classificacao.id"), nullable=True, index=True)
    classificacao_nome = db.Column(String(120), nullable=True, index=True)
    observacao = db.Column(Text, nullable=True)
    justificativa_anomalia = db.Column(Text, nullable=True)

    status = db.Column(String(30), nullable=False, default="EM_PREENCHIMENTO", index=True)
    criado_por = db.Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    criado_em = db.Column(DateTime, nullable=False, default=datetime.now)
    atualizado_em = db.Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    atualizado_por = db.Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    classificacao = db.relationship("PrevisaoClassificacao", lazy="joined")

    __table_args__ = (
        Index("ix_prev_gasto_setor_competencia", "setor", "competencia"),
        Index("ix_prev_gasto_cia_classificacao", "cia", "classificacao_id"),
    )

    @property
    def valor_decimal(self) -> Decimal:
        """Retorna o valor como Decimal para cálculos financeiros seguros."""
        return Decimal(str(self.valor or 0))

    def to_dict(self):
        """
        Serializa o lançamento para a interface.

        A serialização centralizada evita que cada rota exponha diretamente
        objetos ORM e mantém o formato do front-end estável.
        """
        return {
            "id": self.id,
            "setor": self.setor,
            "competencia": self.competencia.isoformat() if self.competencia else None,
            "cia": self.cia,
            "fornecedor": self.fornecedor,
            "vencimento": self.vencimento.isoformat() if self.vencimento else None,
            "valor": float(self.valor_decimal),
            "referencia": self.referencia,
            "classificacao": self.classificacao_nome,
            "observacao": self.observacao,
            "justificativa_anomalia": self.justificativa_anomalia,
            "status": self.status,
            "criado_por": self.criado_por,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "atualizado_em": self.atualizado_em.isoformat() if self.atualizado_em else None,
        }


class PrevisaoHistorico(db.Model):
    """
    Auditoria das alterações de previsão.

    REGRA:
    Alterações financeiras relevantes devem preservar o valor anterior e o novo
    valor para permitir rastreabilidade posterior.
    """

    __tablename__ = "prev_historico"

    id = db.Column(Integer, primary_key=True)
    previsao_id = db.Column(Integer, ForeignKey("prev_gasto.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = db.Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    campo = db.Column(String(80), nullable=False)
    valor_anterior = db.Column(Text, nullable=True)
    valor_novo = db.Column(Text, nullable=True)
    motivo = db.Column(Text, nullable=True)
    data_hora = db.Column(DateTime, nullable=False, default=datetime.now, index=True)


# ============================================================
# BLOCO: EXPORTAÇÃO DE MODELOS
# ============================================================
# A lista explícita facilita importações futuras e torna evidente quais tabelas
# pertencem ao módulo de previsão.
__all__ = [
    "CLASSIFICACOES_INICIAIS",
    "PrevisaoClassificacao",
    "PrevisaoUsuarioSetor",
    "PrevisaoGasto",
    "PrevisaoHistorico",
]

"""
CAMADA 1 — MODELOS DE IDENTIDADE
Representa somente as tabelas necessárias para autenticação e vínculo do usuário.
Os nomes das tabelas permanecem compatíveis com o banco já utilizado pelo ambiente.
"""

from flask_login import UserMixin
from base.core.extensions import db, login_manager


# ============================================================
# ENTIDADE: USUARIO
# Representa a identidade autenticável. Campos legados são mantidos para
# permitir transição gradual sem exigir uma migração estrutural nesta etapa.
# ============================================================
class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    senha_hash = db.Column(db.String(255))
    telefone = db.Column(db.String(20))
    ATIVO = db.Column(db.String(1), default="S")
    ADM = db.Column(db.String(1), default="N")
    reset_token = db.Column(db.String(100), nullable=True)
    token_expiracao = db.Column(db.DateTime, nullable=True)

    vinculos = db.relationship("Usurod", backref="usuario", lazy=True)


# ============================================================
# ENTIDADE: USUROD
# Mantém o vínculo existente entre a conta da aplicação e o identificador
# operacional externo. Não cria uma nova fonte de identidade.
# ============================================================
class Usurod(db.Model):
    __tablename__ = "usurod"

    id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        primary_key=True,
        autoincrement=False,
    )
    resp = db.Column(db.String(100), primary_key=True)


@login_manager.user_loader
def carregar_usuario(user_id):
    # INTEGRAÇÃO: o Flask-Login reconstrói a sessão sempre a partir da tabela
    # de usuários, evitando armazenar credenciais ou dados sensíveis na sessão.
    return db.session.get(Usuario, int(user_id))

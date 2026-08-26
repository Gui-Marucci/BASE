"""
CAMADA 1 — ROTAS DE AUTENTICAÇÃO
Concentra login, cadastro, logout e solicitação de recuperação.
Nenhuma regra das futuras camadas deve ser adicionada aqui.
"""

import hashlib
import os
import re
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from flask_mail import Message
from werkzeug.security import check_password_hash, generate_password_hash

from base.core.auth.models import Usuario, Usurod
from base.core.extensions import db, mail


auth_bp = Blueprint("auth", __name__)
SHA2_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# ============================================================
# BLOCO: VALIDAÇÃO DE CREDENCIAL LEGADA
# Permite reconhecer hashes usados pelo ambiente anterior e migrá-los somente
# depois de uma autenticação válida, sem alterar a senha antes disso.
# ============================================================
def validar_senha(usuario: Usuario, senha: str) -> bool:
    armazenada = (usuario.senha_hash or "").strip()
    if not armazenada:
        return False

    if armazenada.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        try:
            return check_password_hash(armazenada, senha)
        except Exception:
            return False

    if SHA2_RE.fullmatch(armazenada):
        digest = hashlib.sha256(senha.encode("utf-8")).hexdigest()
        if digest.lower() == armazenada.lower():
            usuario.senha_hash = generate_password_hash(senha)
            db.session.commit()
            return True

    if armazenada.startswith("$2"):
        try:
            import bcrypt
            valido = bcrypt.checkpw(senha.encode(), armazenada.encode())
        except Exception:
            valido = False
        if valido:
            usuario.senha_hash = generate_password_hash(senha)
            db.session.commit()
            return True

    return False


# ============================================================
# ROTA: ÍNDICE / LOGIN
# GET exibe a Camada 1; POST autentica e encaminha exclusivamente para a Camada 2.
# ============================================================
@auth_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("index.html")

    # REGRA: o domínio corporativo pode ser omitido pelo usuário, mantendo
    # a conveniência já existente sem deslocar essa regra para o frontend.
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha_hash") or ""
    if email and "@" not in email:
        email = f"{email}@ssonic.com.br"

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not validar_senha(usuario, senha):
        return render_template("index.html", erro="E-mail ou senha inválidos!")

    if str(usuario.ATIVO).upper() == "N":
        return render_template("index.html", erro="Conta desativada!")

    login_user(usuario)
    return redirect(url_for("shell.inicio"))


# ============================================================
# ROTA: CADASTRO
# Mantém a criação da conta compatível com usuarios/usurod, mas separada do shell.
# ============================================================
@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "GET":
        return render_template("cadastro.html")

    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha_hash") or ""
    telefone = (request.form.get("telefone") or "").strip()
    usuario_rodopar = (request.form.get("usuario_rodopar") or "").strip()

    if "@" not in email:
        email = f"{email}@ssonic.com.br"

    if Usuario.query.filter_by(email=email).first():
        flash("Este e-mail já está cadastrado.", "danger")
        return redirect(url_for("auth.cadastro"))

    if not nome or not senha or not usuario_rodopar:
        flash("Preencha os campos obrigatórios.", "danger")
        return redirect(url_for("auth.cadastro"))

    try:
        usuario = Usuario(nome=nome, email=email, senha_hash=generate_password_hash(senha),
                          telefone=telefone, ATIVO="S", ADM="N")
        db.session.add(usuario)
        db.session.flush()
        db.session.add(Usurod(id=usuario.id, resp=usuario_rodopar))
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Não foi possível concluir o cadastro.", "danger")
        return redirect(url_for("auth.cadastro"))

    flash("Cadastro realizado com sucesso!", "success")
    return redirect(url_for("auth.index"))


# ============================================================
# ROTA: SOLICITAÇÃO DE RECUPERAÇÃO
# Gera token de curta duração sem revelar se um endereço existe na base.
# ============================================================
@auth_bp.route("/esqueceu-senha", methods=["GET", "POST"])
def recuperar_senha():
    if request.method == "GET":
        return render_template("recuperar_senha.html")

    email = (request.form.get("email") or "").strip().lower()
    usuario = Usuario.query.filter_by(email=email).first()

    if usuario:
        usuario.reset_token = uuid.uuid4().hex
        usuario.token_expiracao = datetime.now() + timedelta(hours=1)
        db.session.commit()
        try:
            msg = Message("Redefinição de Senha - Supersonic",
                          sender=os.getenv("EMAIL_USER", "sistema@ssonic.com.br"),
                          recipients=[email])
            msg.body = (f"Olá, {usuario.nome}.\n\nSeu código de recuperação é: "
                        f"{usuario.reset_token}\nEste código expira em 1 hora.")
            mail.send(msg)
        except Exception:
            # O registro do token permanece; falhas de SMTP não devem revelar
            # a existência da conta nem quebrar a navegação.
            pass

    flash("Se o e-mail estiver cadastrado, as instruções serão enviadas.", "info")
    return redirect(url_for("auth.recuperar_senha"))


@auth_bp.route("/sair")
@login_required
def sair():
    # Logout centralizado para que as futuras camadas não conheçam detalhes do Flask-Login.
    logout_user()
    return redirect(url_for("auth.index"))

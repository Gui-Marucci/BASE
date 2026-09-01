"""
CAMADA BASE — PONTO DE ENTRADA
Responsabilidade: iniciar somente a nova arquitetura incremental de camadas.
O projeto legado permanece intacto; esta aplicação é uma base paralela para
construção progressiva das novas telas.
"""

import os
from dotenv import load_dotenv
from flask import Flask, app
from base.core.extensions import db, login_manager, mail
from base.core.auth.models import Usuario
from base.core.auth.routes import auth_bp
from base.core.shell.routes import shell_bp
from sqlalchemy.engine import URL
from flask import Flask

<<<<<<< Updated upstream

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

ENV_PATH = os.path.join(
    os.path.dirname(BASE_PATH),
    ".env",
)

if not load_dotenv(ENV_PATH, override=True):
    raise RuntimeError(f"Arquivo .env não encontrado: {ENV_PATH}")
    
=======
app = Flask(
    __name__,
    template_folder="base/templates",
    static_folder="static",
)


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_PATH, ".env")

if not load_dotenv(ENV_PATH, override=True):
    raise RuntimeError(f"Arquivo .env não encontrado: {ENV_PATH}")


>>>>>>> Stashed changes
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_desenvolvimento")

DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "1433"))
DB_NAME = os.getenv("DB_NAME", "Prev_Teste")
DB_DRIVER = os.getenv("DB_DRIVER") or "ODBC Driver 17 for SQL Server"
MODO_DEV = os.getenv("APP_MODO_DEV", "0").strip().lower() in {"1", "true"}
print(
    f"Banco: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} | "
    f"senha carregada: {'sim' if DB_PASSWORD else 'não'} | "
    f"caracteres: {len(DB_PASSWORD)}"
)

url_banco = URL.create(
    "mssql+pyodbc",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    query={
        "driver": DB_DRIVER,
        "TrustServerCertificate": "yes",
    },
)
app.config["SQLALCHEMY_DATABASE_URI"] = str(url_banco)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAIL_SERVER"] = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("EMAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("EMAIL_USER")
app.config["MAIL_PASSWORD"] = os.getenv("EMAIL_PASSWORD")

# ============================================================
# BLOCO: EXTENSÕES COMPARTILHADAS
# Um único objeto de banco, sessão e autenticação serve a todas as camadas.
# Isso evita dependências circulares quando novas funcionalidades forem adicionadas.
# ============================================================
db.init_app(app)
login_manager.init_app(app)
mail.init_app(app)
login_manager.login_view = "auth.login"

# ============================================================
# BLOCO: BLUEPRINTS DA ARQUITETURA
# A camada de autenticação é independente do shell visual e poderá ser mantida
# estável enquanto as camadas 2, 3 e posteriores forem iteradas.
# ============================================================
app.register_blueprint(auth_bp)
app.register_blueprint(shell_bp)

CRIAR_TABELAS = os.getenv(
    "APP_CRIAR_TABELAS",
    "0",
).strip().lower() in {"1", "true"}

if CRIAR_TABELAS:
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=True)

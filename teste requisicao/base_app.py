"""
CAMADA BASE — PONTO DE ENTRADA
Responsabilidade: iniciar somente a nova arquitetura incremental de camadas.
O projeto legado permanece intacto; esta aplicação é uma base paralela para
construção progressiva das novas telas.
"""

import os
from dotenv import load_dotenv
from flask import Flask
from base.core.extensions import db, login_manager, mail
from base.core.auth.models import Usuario
from base.core.auth.routes import auth_bp
from base.core.shell.routes import shell_bp

load_dotenv()

# ============================================================
# BLOCO: CONFIGURAÇÃO DA APLICAÇÃO BASE
# Mantém o mesmo banco configurável do ambiente original, mas sem importar
# rotas, serviços ou modelos funcionais do projeto legado.
# ============================================================
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder="base/templates",
    static_folder="static",
)
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_desenvolvimento")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")
MODO_DEV = os.getenv("APP_MODO_DEV", "0").strip().lower() in {"1", "true"}

if DB_USER and DB_HOST and DB_NAME:
    from urllib.parse import quote_plus
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@"
        f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
elif MODO_DEV:
    caminho = os.path.join(BASE_PATH, "storage", "base_dev.sqlite3")
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{caminho}"
else:
    raise RuntimeError(
        "Configure DB_USER/DB_HOST/DB_NAME ou APP_MODO_DEV=1 para executar a base."
    )

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

with app.app_context():
    # Somente a camada de autenticação é materializada automaticamente em modo dev.
    # Em produção, a estrutura do banco deve ser controlada por migrations.
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=True)

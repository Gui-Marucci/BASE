"""
CAMADA DE INFRAESTRUTURA
Responsabilidade: manter as extensões Flask desacopladas da aplicação.
Novos módulos devem importar estes objetos, nunca criar instâncias próprias.
"""

from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

# ============================================================
# BLOCO: EXTENSÕES GLOBAIS
# Os objetos são inicializados em base_app.py para permitir reutilização
# entre autenticação, shell e futuras camadas sem acoplamento entre módulos.
# ============================================================
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

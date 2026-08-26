"""
CAMADA 2 — INÍCIO E CAMADA 3 — SHELL
A rota de início tem uma única responsabilidade: entregar a superfície vazia
sobre a qual a sidebar compartilhada será aplicada às próximas páginas.
"""

from flask import Blueprint, render_template
from flask_login import login_required

shell_bp = Blueprint("shell", __name__)


# ============================================================
# ROTA: INÍCIO
# Após autenticação, todos os usuários chegam aqui. A página não conhece
# módulos futuros; sua única composição compartilhada é a sidebar.
# ============================================================
@shell_bp.route("/inicio")
@login_required
def inicio():
    return render_template("inicio.html", pagina_ativa="inicio")

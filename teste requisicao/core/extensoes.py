# core/extensoes.py
"""
Extensões compartilhadas do projeto.

Motivo de existir: o app.py criava o SQLAlchemy diretamente (`db = SQLAlchemy(app)`),
o que impedia que outros módulos (ex.: o módulo de Requerimentos) declarassem modelos
sem gerar import circular. Aqui o `db` é criado sem app e ligado depois com
`db.init_app(app)` — comportamento idêntico ao anterior em runtime.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

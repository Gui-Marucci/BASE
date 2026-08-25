# app.py
import os
import shutil
import json
import re
import sys
import hashlib
import uuid
import time
from urllib.parse import quote_plus
from dotenv import load_dotenv
from flask_mail import Mail, Message
from datetime import datetime, timedelta 
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, make_response, send_from_directory
import pandas as pd
from sqlalchemy.orm import joinedload
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from core.extensoes import db
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

# bcrypt usado para reconhecer/verificar hashes $2...
try:
    import bcrypt
except Exception:
    bcrypt = None

load_dotenv()

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# --- Configuração Flask / DB ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_padrao")

# --- Configuração de E-mail --- 
app.config['MAIL_SERVER'] = os.getenv('EMAIL_SMTP', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('EMAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD') 
mail = Mail(app)

print(f"Tentando configurar e-mail para: {app.config['MAIL_USERNAME']}")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")

# MODO_DEV: permite rodar o projeto sem o MySQL corporativo (usa SQLite local).
# Em produção nada muda: com DB_USER/DB_HOST/DB_NAME definidos, usa MySQL como antes.
MODO_DEV = os.getenv("APP_MODO_DEV", "0").strip() in ("1", "true", "True")

if DB_USER and DB_HOST and DB_NAME:
    DB_PASSWORD_ESCAPED = quote_plus(DB_PASSWORD)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ESCAPED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
elif MODO_DEV:
    caminho_sqlite = os.path.join(BASE_PATH, "storage", "dev.sqlite3")
    os.makedirs(os.path.dirname(caminho_sqlite), exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{caminho_sqlite}"
    print("⚠ APP_MODO_DEV ativo: usando banco SQLite local em storage/dev.sqlite3 "
          "(dados de desenvolvimento, não são dados do ERP).")
else:
    raise RuntimeError(
        "Defina DB_USER, DB_HOST e DB_NAME nas variáveis de ambiente (.env) "
        "ou use APP_MODO_DEV=1 para rodar em modo de desenvolvimento com SQLite."
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # limite de upload (anexos)

# O db agora vem de core/extensoes.py (mesmo objeto, apenas compartilhável entre módulos)
db.init_app(app)

login_manager = LoginManager(app)
# Dashboard passa a ser a tela inicial após autenticação.
# Mantém a navegação protegida e evita retorno para a página legada.
login_manager.login_view = "login"

# ---------------------------------------------
#            CLASSE USUARIO
# ----------------------------------------------
class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    senha_hash = db.Column(db.String(255))
    telefone = db.Column(db.String(20))
    ATIVO = db.Column(db.String(1), default='S') # Coluna Ativo
    ADM = db.Column(db.String(1), default='N')   
    reset_token = db.Column(db.String(100), nullable=True) 
    token_expiracao = db.Column(db.DateTime, nullable=True)
    usu_rod = db.relationship('Usurod', backref='usuario_pai', uselist=True)
    

# ---------------------------------------------
#         CLASSE USUARIO DO RODOPAR
# ----------------------------------------------
class Usurod(db.Model):
    __tablename__ = 'usurod'
    id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True, autoincrement=False)
    resp = db.Column(db.String(100), primary_key=True)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# --- Helpers de interface ---
@app.context_processor
def inject_user():
    if current_user.is_authenticated:
        nome = current_user.nome or ""
        partes = nome.split()
        iniciais = (partes[0][0] + partes[-1][0]).upper() if len(partes) > 1 else (partes[0][0].upper() if partes else "")
        return dict(user_nome=nome, user_iniciais=iniciais)
    return dict(user_nome=None, user_iniciais=None)

# --- Função para verificar senha e migrar formatos (Werkzeug, bcrypt, SHA2) ---
SHA2_RE = re.compile(r"^[0-9a-fA-F]{64}$")

def verificar_e_migrar_senha(usuario: Usuario, senha_digitada: str) -> bool:
    stored = (usuario.senha_hash or "").strip()
    if not stored:
        return False

    if stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        try:
            return check_password_hash(stored, senha_digitada)
        except Exception:
            return False

    if stored.startswith("$2"):
        if bcrypt is None:
            return False
        try:
            ok = bcrypt.checkpw(senha_digitada.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            ok = False
        if ok:
            try:
                usuario.senha_hash = generate_password_hash(senha_digitada)
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True
        return False

    if SHA2_RE.match(stored):
        digest = hashlib.sha256(senha_digitada.encode("utf-8")).hexdigest().lower()
        if digest == stored.lower():
            try:
                usuario.senha_hash = generate_password_hash(senha_digitada)
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True
        return False

    return False

# -----------------------------
# STORAGE FORA DE `static/`
# -----------------------------

STORAGE_DIR = os.path.join(BASE_PATH, "storage")
STATIC_STORAGE_DIR = os.path.join(BASE_PATH, "static", "storage")

STORAGE_JSON_FILES = [
    "base_dados.json",
    "dados_completos.json",
    "posicoes_veiculos_3S.json",
    "posicoes_veiculos_at.json",
    "veiculos_resumo_3S.json",
    "veiculos_sem_posicao_422.json",
]

def _migrar_storage_de_static_para_storage() -> None:
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        for fname in STORAGE_JSON_FILES:
            src = os.path.join(STATIC_STORAGE_DIR, fname)
            dst = os.path.join(STORAGE_DIR, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
                print(f"✔ Migrado: {fname} para /storage")
    except Exception as e:
        print(f"⚠ Falha na migração de arquivos do storage: {e}")

_migrar_storage_de_static_para_storage()

@app.route("/storage/<path:filename>")
def storage_file(filename: str):
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        abort(400)
    if not safe_filename.lower().endswith(".json"):
        abort(404)

    file_path = os.path.join(STORAGE_DIR, safe_filename)
    if not os.path.exists(file_path):
        abort(404)

    resp = make_response(send_from_directory(STORAGE_DIR, safe_filename))
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/cadastro")
def cadastro():
    return render_template("cadastro.html")

@app.route("/dados_gerais")
@login_required
def dados_gerais():
    filtros = request.args.to_dict()
    pesquisa_geral = request.args.get('pesquisa_geral', '').strip().upper()
    campos_especificos = request.args.getlist('campo_filtro[]')
    valores_especificos = request.args.getlist('valor_filtro[]')
    
    json_path = os.path.join(STORAGE_DIR, "dados_completos.json")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            dados_lidos = json.load(f)
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")
        dados_lidos = []

    if str(current_user.ADM).strip().upper() == 'S':
        dados_filtrados_usuario = dados_lidos
    else:
        vinculos = Usurod.query.filter_by(id=current_user.id).all()
        lista_resp_validos = [v.resp.strip().upper() for v in vinculos if v.resp and v.resp.strip()]
        
        if lista_resp_validos:
            dados_filtrados_usuario = [
                item for item in dados_lidos
                if item.get('RESPONSAVEL_SAC') and str(item.get('RESPONSAVEL_SAC')).strip().upper() in lista_resp_validos
            ]
        else:
            dados_filtrados_usuario = dados_lidos

    resultados = dados_filtrados_usuario

    if pesquisa_geral:
        resultados = [
            item for item in resultados 
            if any(pesquisa_geral in str(v).upper() for v in item.values())
        ]

    mapeamento_colunas = {
        "TIPO DO DOCUMENTO": "TIPO",
        "CÓDIGO DO PAGADOR": "CODPAG",
        "DESCRIÇÃO DO PAGADOR": "DESPAG",
        "PAGADOR":"DESPAG",
        "RAIZ DO CNPJ": "RAIZ",
        "NOME DO COLABORADOR": "NOME_COLABORADOR",
        "TELEFONE DO COLABORADOR": "TELEFONE_COLABORADOR",
        "CAVALO": "CAVALO",
        "FROTA": "FROTA",
        "PLACA": "PLACA_CAR",
        "CHAVE DO MANIFESTO": "CHAVE_MAN",
        "DATA": "DATCAD",
        "CÓDIGO DO CONHECIMENTO": "CODCON",
        "CHAVE DO CONHECIMENTO": "CHAVE_CON",
        "SÉRIE DA NOTA": "SERIEN",
        "NÚMERO DA NOTA": "NOTFIS",
        "CHAVE DA NOTA":"NOTNFE",
        "DATA DA NOTA FISCAL": "DATNOT",
        "QUANTIDADE": "QUANTI",
        "M³(METRAGEM CÚBICA)": "PESCUB",
        "PESO CALCULADO": "PESCAL",
        "VALOR DA MERCADORIA": "VLRMER",
        "NOME DO REMETENTE": "DESREM",
        "CPF/CNPJ DO REMETENTE": "CPF_CNPJ_REM",
        "CÓDIGO DO DESTINATÁRIO": "CODDEST",
        "NOME DO DESTINATÁRIO": "DESDES",
        "CPF/CNPJ DO DESTINATÁRIO": "CPF_CNPJ_DEST",
        "CÓDIGO DO MUNICÍPIO": "CODMUN",
        "MUNICÍPIO DO DESTINATÁRIO": "MDEST",
        "REGIÃO DO DESTINATÁRIO": "REGDES",
        "TERMINAL DE ENTREGA": "DESENT",
        "MUNICÍPIO DO TERMINAL": "MENT",
        "NOME DO REDESPACHO": "DESRED",
        "MUNICÍPIO DO REDESPACHO": "MRED",
        "ÚLTIMA OCORRÊNCIA": "ULTOCO",
        "ATENDENTE": "RESPONSAVEL_SAC",
        "INFORMAÇÃO DO PALETE": "OBSPLT",
        "FRETE": "TOTFRE",
        "MODALIDADE": "MODALIDADE",
    }

    for campo, valor in zip(campos_especificos, valores_especificos):
        if campo and valor:
            campo_bruto = campo.strip().upper()
            chave_coluna = mapeamento_colunas.get(campo_bruto, campo_bruto)
            valor_limpo = valor.strip().upper()
            resultados = [
                item for item in resultados 
                if valor_limpo in str(item.get(chave_coluna, '')).upper()
            ]

    return render_template("dados_gerais.html", 
                           dados=resultados,
                           user_nome=getattr(current_user, 'nome', 'Usuário'),
                           user_iniciais=getattr(current_user, 'nome', 'US')[:2].upper())

# ---------------------------------------------------------------------------
# TELA LEGADA (mapa de veículos que ocupava /requerimento)
#
# A rota /requerimento passou a ser a área de Requerimentos (core/req_routes.py).
# A tela antiga NÃO foi apagada: continua disponível aqui e o template foi movido
# para templates/legado/requerimento_mapa.html. O mapa completo também continua
# em /mapaboard, que nunca deixou de existir.
# ---------------------------------------------------------------------------
@app.route("/legado/requerimento-mapa")
@login_required
def requerimento_mapa_legado():
    json_path = os.path.join(STORAGE_DIR, "dados_completos.json")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            dados_lidos = json.load(f)
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")
        dados_lidos = []

    if str(current_user.ADM).strip().upper() == 'S':
        dados_filtrados = dados_lidos
    else:
        vinculo = Usurod.query.filter_by(id=current_user.id).first()
        if vinculo:
            login_vinculado = str(vinculo.resp).strip().upper()
            dados_filtrados = [
                item for item in dados_lidos 
                if str(item.get('RESPONSAVEL_SAC', '')).strip().upper() == login_vinculado
            ]
        else:
            dados_filtrados = []

    return render_template("legado/requerimento_mapa.html",
                           dados=dados_filtrados,
                           user_nome=getattr(current_user, 'nome', 'Usuário'),
                           user_iniciais=getattr(current_user, 'nome', 'US')[:2].upper())


# Compatibilidade: qualquer url_for('requerimento') remanescente continua funcionando
# e leva o usuário para a nova área de requerimentos.
@app.route("/abrir-requerimento")
@login_required
def requerimento():
    return redirect(url_for("req.novo"))

@app.route('/comprovante')
@login_required 
def comprovante():
    return render_template('comprovante.html', user_iniciais="JS")

# --- CONFIGURAÇÃO GOOGLE DRIVE ---
SERVICE_ACCOUNT_FILE = os.path.join(BASE_PATH, 'core_drive', 'credenciais_api_drive.json')
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
PASTA_DRIVE_ID = '1YFQGgkvoOH0zcgWK4HRdFcxDsRk0pjjz'

def obter_id_drive_por_nota_inteligente(chave_longa, nota_curta):
    try:
        token_path = os.path.join(BASE_PATH, 'core_drive', 'token.json')
        if not os.path.exists(token_path):
            print("DEBUG: token.json não encontrado.")
            return None

        creds = Credentials.from_authorized_user_file(token_path)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())

        service = build('drive', 'v3', credentials=creds)

        chave_l = str(chave_longa).strip()
        nota_c = str(nota_curta).strip()
        
        query_pasta = f"'{PASTA_DRIVE_ID}' in parents and trashed = false"
        
        for tentativa in range(2):
            print(f"DEBUG: Tentativa {tentativa + 1} de busca para: {nota_c}")
            results = service.files().list(
                q=query_pasta, 
                fields="files(id, name)",
                pageSize=1000
            ).execute()
            
            items = results.get('files', [])
            
            for f in items:
                nome_drive = f['name'].upper()
                if nota_c in nome_drive or (chave_l and chave_l in nome_drive):
                    print(f"DEBUG: ACHOU via listagem direta! Nome: {f['name']}")
                    return f['id']
            
            if tentativa == 0:
                time.sleep(2)

        query_global = f"(name contains '{chave_l}' or name contains '{nota_c}') and trashed = false"
        results_global = service.files().list(q=query_global, fields="files(id, name)").execute()
        items_global = results_global.get('files', [])
        
        if items_global:
            print(f"DEBUG: ACHOU via busca global! Nome: {items_global[0]['name']}")
            return items_global[0]['id']

        print("DEBUG: Arquivo não encontrado no Drive após todas as tentativas.")
        return None

    except Exception as e:
        print(f"DEBUG: Erro crítico ao acessar Google Drive: {e}")
        return None

@app.route('/api/buscar-pod')
@login_required 
def buscar_pod():
    nota_numero = request.args.get('nota')
    if not nota_numero:
        return jsonify({"erro": "Nota não informada"}), 400

    chave_notnfe = ""
    json_path = os.path.join(STORAGE_DIR, "dados_completos.json")
    
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                dados_lidos = json.load(f)
                for item in dados_lidos:
                    if str(item.get("NOTFIS", "")).strip() == str(nota_numero).strip():
                        chave_notnfe = str(item.get("NOTNFE", "")).strip()
                        break
    except Exception as e:
        print(f"DEBUG: Erro ao ler JSON: {e}")

    id_encontrado = obter_id_drive_por_nota_inteligente(chave_notnfe, nota_numero)

    dados_comprovante = {
        "numeronota": nota_numero,
        "recebedor": "IDENTIFICADO VIA DRIVE" if id_encontrado else "NÃO LOCALIZADO",
        "dtfinalizacao": datetime.now().strftime("%d/%m/%Y %H:%M") if id_encontrado else "---",
        "documento": chave_notnfe or nota_numero,
        "aprovador": "Sistema Supersonic",
        "canhotoaprovado": "S" if id_encontrado else "PENDENTE", # Mudamos de 'N' para 'PENDENTE'
        "canhotoemanalise": "N",
        "motivorecusa": None,
        "imagensnf": []
    }

    if id_encontrado:
        url_final = f"https://drive.google.com/file/d/{id_encontrado}/preview"
        dados_comprovante["imagensnf"].append({"tipoimagem": "PDF", "urlimagem": url_final})
    else:
        dados_comprovante["imagensnf"].append({
            "tipoimagem": "AVISO", 
            "urlimagem": "https://via.placeholder.com/400x600?text=Comprovante+em+Processamento"
        })

    return jsonify(dados_comprovante)

@app.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q", "").strip()
    data_filtro = request.args.get("data", "").strip()
    exact_flag = request.args.get("exact", "0") == "1"

    if not q and not data_filtro:
        return jsonify([])

    resultados = []
    json_path = os.path.join(STORAGE_DIR, "dados_completos.json")

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                dados_json = json.load(f)
            
            data_formatada = ""
            if data_filtro:
                partes = data_filtro.split('-')
                data_formatada = f"{partes[2]}/{partes[1]}/{partes[0]}"

            for entry in dados_json:
                notfis = str(entry.get("NOTFIS", "")).strip()
                notnfe = str(entry.get("NOTNFE", "")).strip()
                data_item = str(entry.get("DT_INTEGRACAO", "")).strip() 

                match_nota = True
                if q:
                    if exact_flag:
                        match_nota = (q == notfis or q == notnfe)
                    else:
                        match_nota = (q.lower() in notfis.lower() or q.lower() in notnfe.lower())
                else:
                    match_nota = True

                match_data = True
                if data_formatada:
                    match_data = (data_formatada in data_item)

                if match_nota and match_data:
                    resultados.append({
                        "SERIEN": entry.get("SERIEN"),
                        "NOTFIS": entry.get("NOTFIS"),
                        "NOTNFE": entry.get("NOTNFE"),
                        "DESPAG": entry.get("DESPAG")
                    })

            return jsonify(resultados)

        except Exception as e:
            print(f"Erro na busca: {e}")
            return jsonify({"error": str(e)}), 500
            
    return jsonify([])

@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    nome = request.form.get("nome")
    email = request.form.get("email")
    senha_bruta = request.form.get("senha_hash")
    telefone = request.form.get("telefone")
    nome_rodopar = request.form.get("usuario_rodopar")

    try:
        usuario_existe = Usuario.query.filter_by(email=email).first()
        if usuario_existe:
            flash("Este e-mail já está cadastrado!")
            return redirect(url_for("cadastro"))

        senha_com_hash = generate_password_hash(senha_bruta)
        novo_usuario = Usuario(
            nome=nome, 
            email=email, 
            senha_hash=senha_com_hash,
            telefone=telefone,
            ATIVO='S',
            ADM='N')

        db.session.add(novo_usuario)
        db.session.flush() 

        novo_rodopar = Usurod(id=novo_usuario.id, resp=nome_rodopar)
        db.session.add(novo_rodopar)

        db.session.commit()

        flash("Cadastro realizado com sucesso!")
        return redirect(url_for("index"))

    except Exception as e:
        db.session.rollback()
        print(f"Erro detalhado: {e}")
        return f"Erro ao salvar no banco: {e}"     

@app.route("/esqueceu-senha", methods=["GET", "POST"])
def recuperar_senha():
    if request.method == "POST":
        email = request.form.get("email")
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario:
            token = str(uuid.uuid4())
            usuario.reset_token = token
            usuario.token_expiracao = datetime.now() + timedelta(hours=1)
            db.session.commit()
            
            msg = Message("Redefinição de Senha - Supersonic",
                          sender="sistema@ssonic.com.br",
                          recipients=[email])
            
            msg.html = '''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f9f9f9;">
                <h2 style="color: #0056b3; text-align: center;">Recuperação de Senha</h2>
                <p>Olá, <strong>{nome}</strong>.</p>
                <p>Recebemos uma solicitação para redefinir sua senha. Utilize o código abaixo:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <span style="font-size: 24px; font-weight: bold; background: #ffffff; padding: 15px 30px; border-radius: 8px; border: 1px dashed #0056b3;">
                        {token}
                    </span>
                </div>
                <p style="color: #64748b; font-size: 0.9rem;">Este código expira em 1 hora.</p>
            </div>
            '''.format(nome=usuario.nome, token=token)
            
            try:
                mail.send(msg)
                flash("E-mail enviado com sucesso!", "success")
            except Exception as e:
                print(f"ERRO NO ENVIO: {e}") 
                flash("Erro ao enviar e-mail. Tente novamente mais tarde.", "danger")
        else:
            flash("E-mail não encontrado em nossa base.", "danger")
            
    return render_template("recuperar_senha.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        senha_digitada = request.form.get("senha_hash")

        if "@" not in email:
            email = email + "@ssonic.com.br"
        
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and verificar_e_migrar_senha(usuario, senha_digitada):
            if usuario.ATIVO == 'N':
                flash("Sua conta está desativada. Procure o ADM.", "danger")
                return render_template("index.html", erro="Conta desativada!")
            
            login_user(usuario)
            if usuario.email == 'tv@ssonic.com.br':
                return redirect(url_for('dashboard')) 
            else:
                return redirect(url_for("req.dashboard"))
            
        return render_template("index.html", erro="E-mail ou senha inválidos!")
    
    return render_template("index.html")

@app.route("/sair")
def sair():
    logout_user()
    return redirect(url_for("index"))

@app.route("/perfil")
@login_required
def perfil():
    if current_user.ADM == 'S':
        json_path = os.path.join(STORAGE_DIR, 'dados_completos.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Erro ao ler JSON: {e}")
            data = []
        
        mapa_metricas = {}
        for item in data:
            responsavel_json = item.get('RESPONSAVEL_SAC')
            if responsavel_json:
                chave = str(responsavel_json).strip().upper()
                if chave not in mapa_metricas:
                    mapa_metricas[chave] = {'filial': item.get('FILIAL_RESP', 'N/A'), 'qtd': 0}
                mapa_metricas[chave]['qtd'] += 1
        
        todos_usuarios = Usuario.query.options(joinedload(Usuario.usu_rod)).all()
        lista_final = []
        
        for user in todos_usuarios:
            logins_atribuidos = []
            total_clientes = 0
            filial_detectada = "Não encontrada"

            for vinculo in user.usu_rod:
                login_nome = vinculo.resp
                chave_busca = str(login_nome).strip().upper()
                
                metrica = mapa_metricas.get(chave_busca, {'filial': 'Não encontrada', 'qtd': 0})
                
                total_clientes += metrica['qtd']
                
                if metrica['filial'] != 'Não encontrada' and filial_detectada == "Não encontrada":
                    filial_detectada = metrica['filial']

                logins_atribuidos.append({'login': login_nome})
            
            lista_final.append({
                'id': user.id,
                'nome': user.nome,
                'status': user.ATIVO,
                'filial': filial_detectada,
                'qtd_clientes': total_clientes,
                'vinculos': logins_atribuidos
            })

            filiais_para_filtro = sorted(list(set(u['filial'] for u in lista_final if u['filial'] != "Não encontrada")))
            
        return render_template("perfil_adm.html", usuarios=lista_final, filiais=filiais_para_filtro)
    else:
        return render_template("perfil_atendente.html")

@app.route("/desativar_usuario/<int:user_id>", methods=["POST"])
@login_required
def desativar_usuario(user_id):
    if current_user.ADM != 'S':
        flash("Acesso negado!", "danger")
        return redirect(url_for('perfil'))
    
    if user_id == current_user.id:
        flash("Você não pode desativar sua própria conta!", "danger")
        return redirect(url_for('perfil'))

    usuario = Usuario.query.get_or_404(user_id)
    novo_status = request.form.get('novo_status')
    
    if novo_status in ['S', 'N']:
        usuario.ATIVO = novo_status 
        db.session.commit()
        
        msg = "REATIVADO" if novo_status == 'S' else "DESATIVADO"
        cat = "success" if novo_status == 'S' else "warning"
        flash(f"O usuário {usuario.nome} foi {msg} com sucesso!", cat)
    
    return redirect(url_for('perfil'))

@app.route('/primeira')
@login_required
def painel():
    # Página legada mantida apenas por compatibilidade.
    # O fluxo oficial agora inicia no Dashboard de Requerimentos.
    return redirect(url_for("req.dashboard"))
    json_path = os.path.join(STORAGE_DIR, "dados_completos.json")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            dados_json = json.load(f)
    except Exception as e:
        dados_json = []

    if str(current_user.ADM).strip().upper() == 'S':
        clientes_finais = dados_json
    else:
        vinculos = Usurod.query.filter_by(id=current_user.id).all()
        lista_logins = [str(v.resp).strip().upper() for v in vinculos]
        
        clientes_finais = [
            c for c in dados_json 
            if str(c.get('RESPONSAVEL_SAC', '')).strip().upper() in lista_logins
        ]

    return render_template("primeira.html", clientes=clientes_finais)

@app.route("/alterar_vinculo/<int:user_id>", methods=["POST"])
@login_required
def alterar_vinculo(user_id):
    if current_user.ADM != 'S':
        return redirect(url_for('perfil'))
    novo_resp = request.form.get('novo_resp').strip().upper()
    if novo_resp:
        ja_existe = Usurod.query.filter_by(id=user_id, resp=novo_resp).first()
        if not ja_existe:
            novo_vinculo = Usurod(id=user_id, resp=novo_resp)
            db.session.add(novo_vinculo)
            db.session.commit()
            flash(f"Login {novo_resp} ADICIONADO com sucesso!", "success")
        else:
            flash(f"O login {novo_resp} já está atribuído a este usuário!", "warning")

    return redirect(url_for('perfil'))

@app.route("/remover_vinculo_direto/<int:user_id>/<string:resp_nome>", methods=["POST"])
@login_required
def remover_vinculo_direto(user_id, resp_nome):
    if current_user.ADM != 'S':
        return redirect(url_for('perfil'))
    
    vinculo = Usurod.query.filter_by(id=user_id, resp=resp_nome).first()
    
    if vinculo:
        db.session.delete(vinculo)
        db.session.commit()
        flash(f"Login {resp_nome} removido!", "success")
    else:
        flash("Vínculo não encontrado.", "warning")
    
    return redirect(url_for('perfil'))

@app.route("/salvar-telefone", methods=["POST"])
@login_required
def salvar_telefone():
    if current_user.ADM == 'S':
        flash("Acesso negado", "danger")
        return redirect(url_for('perfil'))
    
    telefone = request.form.get("telefone")
    current_user.telefone = telefone
    db.session.commit()
    flash("Telefone atualizado com sucesso!", "success")
    return redirect(url_for('perfil'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Página de dashboard para usuários com perfil ADM ou TV. 
    if current_user.ADM == 'S' or current_user.ADM == 'N':
        #Tirar or e manter a verificação original no patch 
        is_tv_user = (current_user.email == 'tv@ssonic.com.br') 

        json_path = os.path.join(STORAGE_DIR, 'dados_completos.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            data = []

        tipo = 'TV' if is_tv_user else 'ADM'
        
        return render_template('Dashboard.html', data=data, user_type=tipo)
    
    return "Acesso negado", 403

@app.route('/mapaboard')
@login_required
def mapaboard():
    json_path = os.path.join(STORAGE_DIR, "dados_completos.json")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            dados_lidos = json.load(f)
    except Exception as e:
        print(f"Erro ao ler JSON para o mapa: {e}")
        dados_lidos = []

    is_tv_user = (current_user.email == 'tv@ssonic.com.br')
    
    if str(current_user.ADM).strip().upper() == 'S':
        dados_filtrados = dados_lidos
    else:
        vinculo = Usurod.query.filter_by(id=current_user.id).first()
        if vinculo:
            login_vinculado = str(vinculo.resp).strip().upper()
            dados_filtrados = [
                item for item in dados_lidos 
                if str(item.get('RESPONSAVEL_SAC', '')).strip().upper() == login_vinculado
            ]
        else:
            dados_filtrados = []

    tipo = 'TV' if is_tv_user else ('ADM' if current_user.ADM == 'S' else 'USER')
    
    return render_template('Dashboard.html', dados=dados_filtrados, user_type=tipo)
   
# ---------------------------------------------------------------------------
# MÓDULO DE REQUERIMENTOS
# Registrado por último para reaproveitar db, login_manager e templates existentes.
# ---------------------------------------------------------------------------
from core.req_routes import req_bp          # noqa: E402  (import após a criação do app)
from core import req_models                  # noqa: E402,F401  (registra os modelos req_*)

app.register_blueprint(req_bp)


def criar_tabelas_requerimentos() -> None:
    """Cria SOMENTE as tabelas novas (prefixo req_) se ainda não existirem.

    Não toca em `usuarios` nem em `usurod`. Em produção, prefira rodar
    migrations/001_requerimentos.sql; esta função é a rede de segurança e o
    caminho usado no modo de desenvolvimento.
    """
    with app.app_context():
        tabelas = [
            tabela for nome, tabela in db.metadata.tables.items()
            if nome.startswith("req_")
        ]
        db.metadata.create_all(bind=db.engine, tables=tabelas, checkfirst=True)


if os.getenv("REQ_AUTO_CREATE", "1").strip() in ("1", "true", "True"):
    try:
        criar_tabelas_requerimentos()
    except Exception as erro:
        print(f"⚠ Não foi possível verificar/criar as tabelas de requerimentos: {erro}")


@app.template_filter("moeda")
def filtro_moeda(valor) -> str:
    """Formata número em Real brasileiro (R$ 1.234,56)."""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        numero = 0.0
    texto = f"{numero:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {texto}"


@app.template_filter("data_br")
def filtro_data_br(valor) -> str:
    if not valor:
        return "—"
    try:
        return valor.strftime("%d/%m/%Y")
    except AttributeError:
        return str(valor)


@app.template_filter("data_hora_br")
def filtro_data_hora_br(valor) -> str:
    if not valor:
        return "—"
    try:
        return valor.strftime("%d/%m/%Y %H:%M")
    except AttributeError:
        return str(valor)


if __name__ == "__main__":
    # host='0.0.0.0' libera o acesso para a rede interna
    app.run(host='0.0.0.0', port=5000)
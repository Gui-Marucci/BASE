"""
MÓDULO: PREVISÃO DE GASTOS

Rotas de tela e API do planejamento orçamentário.
"""

from datetime import date
from io import BytesIO

import pandas as pd
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from core.extensoes import db
from core.previsao_models import PrevisaoGasto, PrevisaoHistorico, PrevisaoClassificacao
from core import previsao_service as servico

previsao_bp = Blueprint("previsao", __name__, url_prefix="/previsao")


# ============================================================
# BLOCO: HELPERS
# ============================================================

def _erro(mensagem, status=400):
    """Padroniza respostas de erro para as APIs do módulo."""
    return jsonify({"ok": False, "erro": mensagem}), status


def _parse_data(valor):
    """Converte datas vindas de formulário/planilha para date sem quebrar a importação."""
    if valor is None or str(valor).strip() == "":
        return None
    try:
        return pd.to_datetime(valor, dayfirst=True).date()
    except Exception:
        return None


def _parse_valor(valor):
    """Converte formatos monetários brasileiros e numéricos para float."""
    if valor is None or str(valor).strip() == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _normalizar_coluna(nome):
    """Normaliza cabeçalhos para identificação flexível durante importação."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.upper().replace("_", " ").split())


# MAPEAMENTO: nomes aceitos pela planilha fictícia e futuras variações.
MAPA_COLUNAS = {
    "CIA": ["CIA", "COMPANHIA", "EMPRESA"],
    "FORNECEDORES": ["FORNECEDORES", "FORNECEDOR", "SUPPLIER"],
    "VENCTO": ["VENCTO", "VENCIMENTO", "DATA DE VENCIMENTO", "VENC"],
    "VALOR": ["VALOR", "VALOR PREVISTO", "VALOR TOTAL"],
    "REFERENCIA DO SERVICO PRODUTO": [
        "REFERENCIA DO SERVICO PRODUTO", "REFERENCIA SERVICO PRODUTO",
        "DESCRICAO DO GASTO", "DESCRICAO", "REFERENCIA"
    ],
    "CLASSIFICACAO PAGAMENTOS OPERACIONAIS": [
        "CLASSIFICACAO PAGAMENTOS OPERACIONAIS", "CLASSIFICACAO PAGAMENTOS",
        "CLASSIFICACAO", "CATEGORIA"
    ],
    "SETOR": ["SETOR", "DEPARTAMENTO", "AREA"],
}


def identificar_colunas(colunas):
    """
    Identifica automaticamente cabeçalhos sem depender da posição física.

    Retorna um mapa campo_de_negocio -> coluna_original. Colunas não
    identificadas permanecem disponíveis para mapeamento manual.
    """
    normalizadas = {_normalizar_coluna(c): c for c in colunas}
    resultado = {}
    for campo, aliases in MAPA_COLUNAS.items():
        for alias in aliases:
            if _normalizar_coluna(alias) in normalizadas:
                resultado[campo] = normalizadas[_normalizar_coluna(alias)]
                break
    return resultado


# ============================================================
# BLOCO: TELAS
# ============================================================

@previsao_bp.route("/")
@login_required
def index():
    """Exibe a central de previsões com filtros e indicadores consolidados."""
    filtros = {k: request.args.get(k, "") for k in ("setor", "cia", "fornecedor", "classificacao")}
    dados = servico.consolidar(filtros)
    query = PrevisaoGasto.query
    if filtros["setor"]:
        query = query.filter_by(setor=filtros["setor"])
    if filtros["cia"]:
        query = query.filter_by(cia=filtros["cia"])
    if filtros["fornecedor"]:
        query = query.filter_by(fornecedor=filtros["fornecedor"])
    if filtros["classificacao"]:
        query = query.filter_by(classificacao_nome=filtros["classificacao"])
    registros = query.order_by(PrevisaoGasto.competencia.desc(), PrevisaoGasto.vencimento.asc()).limit(500).all()
    return render_template(
        "previsao/index.html",
        pagina_ativa="previsao_gastos",
        titulo_pagina="Previsão de Gastos",
        registros=registros,
        indicadores=dados,
        setores=servico.setores_permitidos(current_user),
        classificacoes=PrevisaoClassificacao.query.filter_by(ativa=True).order_by(PrevisaoClassificacao.nome).all(),
        filtros=filtros,
    )


@previsao_bp.route("/novo")
@login_required
def novo():
    """Abre o formulário manual de um lançamento de previsão."""
    return render_template(
        "previsao/novo.html",
        pagina_ativa="previsao_gastos",
        titulo_pagina="Nova Previsão de Gasto",
        setores=servico.setores_permitidos(current_user),
        classificacoes=PrevisaoClassificacao.query.filter_by(ativa=True).order_by(PrevisaoClassificacao.nome).all(),
    )


@previsao_bp.route("/importar")
@login_required
def importar():
    """Exibe o fluxo de importação, que somente persiste após confirmação."""
    return render_template(
        "previsao/importar.html",
        pagina_ativa="previsao_gastos",
        titulo_pagina="Importar Previsão",
        setores=servico.setores_permitidos(current_user),
    )


# ============================================================
# BLOCO: API DE CADASTRO
# ============================================================

@previsao_bp.route("/api", methods=["POST"])
@login_required
def criar():
    """Cria um lançamento manual após validar setor, valor e classificação."""
    dados = request.get_json(silent=True) or request.form.to_dict()
    resultado = servico.validar_lancamento(dados, current_user)
    if resultado["erros"]:
        return jsonify({"ok": False, **resultado}), 400

    classificacao = servico.obter_classificacao(dados.get("classificacao"))
    if not classificacao:
        return _erro("A classificação informada não existe no catálogo.")

    competencia = _parse_data(dados.get("competencia"))
    if not competencia:
        return _erro("Período de competência inválido ou não informado.")

    valor = _parse_valor(dados.get("valor"))
    registro = PrevisaoGasto(
        setor=servico.normalizar_texto(dados.get("setor")),
        competencia=competencia,
        cia=servico.normalizar_texto(dados.get("cia")),
        fornecedor=servico.normalizar_texto(dados.get("fornecedor")),
        vencimento=_parse_data(dados.get("vencimento")),
        valor=valor,
        referencia=servico.normalizar_texto(dados.get("referencia")),
        classificacao_id=classificacao.id,
        classificacao_nome=classificacao.nome,
        observacao=servico.normalizar_texto(dados.get("observacao")),
        criado_por=current_user.id,
        atualizado_por=current_user.id,
    )
    db.session.add(registro)
    db.session.commit()
    return jsonify({
        "ok": True,
        "registro": registro.to_dict(),
        "anomalia": servico.analisar_anomalia(dados),
    }), 201


# ============================================================
# BLOCO: API DE IMPORTAÇÃO
# ============================================================

@previsao_bp.route("/api/importar", methods=["POST"])
@login_required
def analisar_importacao():
    """
    Lê a planilha e devolve somente uma prévia validada.

    REGRA CRÍTICA:
    Esta rota nunca grava lançamentos. A persistência ocorre em confirmar_importacao.
    """
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return _erro("Selecione uma planilha para importar.")

    setor_padrao = servico.normalizar_texto(request.form.get("setor"))
    try:
        df = pd.read_excel(BytesIO(arquivo.read()), sheet_name=request.form.get("aba") or 0)
    except Exception as erro:
        return _erro(f"Não foi possível ler a planilha: {erro}")

    identificadas = identificar_colunas(df.columns)
    obrigatorias = ["VALOR", "CLASSIFICACAO PAGAMENTOS OPERACIONAIS"]
    faltantes = [campo for campo in obrigatorias if campo not in identificadas]
    if faltantes:
        return jsonify({
            "ok": False,
            "etapa": "MAPEAMENTO",
            "erro": "Não foi possível identificar todas as colunas obrigatórias.",
            "faltantes": faltantes,
            "colunas": [str(c) for c in df.columns],
            "identificadas": identificadas,
        }), 422

    linhas = []
    erros = []
    alertas = []
    for indice, (_, linha) in enumerate(df.iterrows(), start=2):
        dados = {
            "setor": setor_padrao or (linha.get(identificadas.get("SETOR")) if identificadas.get("SETOR") else ""),
            "cia": linha.get(identificadas.get("CIA")) if identificadas.get("CIA") else "",
            "fornecedor": linha.get(identificadas.get("FORNECEDORES")) if identificadas.get("FORNECEDORES") else "",
            "vencimento": linha.get(identificadas.get("VENCTO")) if identificadas.get("VENCTO") else "",
            "valor": linha.get(identificadas.get("VALOR")),
            "referencia": linha.get(identificadas.get("REFERENCIA DO SERVICO PRODUTO")) if identificadas.get("REFERENCIA DO SERVICO PRODUTO") else "",
            "classificacao": linha.get(identificadas.get("CLASSIFICACAO PAGAMENTOS OPERACIONAIS")),
        }
        dados["vencimento"] = _parse_data(dados["vencimento"])
        dados["valor"] = _parse_valor(dados["valor"])
        validacao = servico.validar_lancamento(dados, current_user)
        anomalia = servico.analisar_anomalia(dados)
        linhas.append({**dados, "linha_planilha": indice, "anomalia": anomalia})
        erros.extend([{ "linha": indice, "mensagem": e } for e in validacao["erros"]])
        alertas.extend([{ "linha": indice, "mensagem": a } for a in validacao["alertas"]])

    return jsonify({
        "ok": True,
        "etapa": "REVISAO",
        "linhas": linhas,
        "erros": erros,
        "alertas": alertas,
        "resumo": {
            "total": len(linhas),
            "validos": len(linhas) - len({e["linha"] for e in erros}),
            "erros": len({e["linha"] for e in erros}),
            "alertas": len({a["linha"] for a in alertas}),
        },
        "identificadas": identificadas,
    })


@previsao_bp.route("/api/importar/confirmar", methods=["POST"])
@login_required
def confirmar_importacao():
    """
    Persiste uma prévia já revisada pelo usuário.

    TRANSAÇÃO:
    Se qualquer registro obrigatório falhar, toda a operação é revertida para
    evitar importação parcial.
    """
    payload = request.get_json(silent=True) or {}
    linhas = payload.get("linhas") or []
    if not linhas:
        return _erro("Nenhum lançamento foi enviado para confirmação.")

    registros = []
    try:
        for dados in linhas:
            validacao = servico.validar_lancamento(dados, current_user)
            if validacao["erros"]:
                raise ValueError(f"Linha {dados.get('linha_planilha')}: {'; '.join(validacao['erros'])}")
            classificacao = servico.obter_classificacao(dados.get("classificacao"))
            if not classificacao:
                raise ValueError(f"Classificação inexistente: {dados.get('classificacao')}")
            competencia = _parse_data(dados.get("competencia")) or _parse_data(dados.get("vencimento"))
            if not competencia:
                raise ValueError(f"Linha {dados.get('linha_planilha')}: informe o período de competência.")
            registro = PrevisaoGasto(
                setor=servico.normalizar_texto(dados.get("setor")),
                competencia=competencia,
                cia=servico.normalizar_texto(dados.get("cia")),
                fornecedor=servico.normalizar_texto(dados.get("fornecedor")),
                vencimento=_parse_data(dados.get("vencimento")),
                valor=_parse_valor(dados.get("valor")),
                referencia=servico.normalizar_texto(dados.get("referencia")),
                classificacao_id=classificacao.id,
                classificacao_nome=classificacao.nome,
                criado_por=current_user.id,
                atualizado_por=current_user.id,
            )
            db.session.add(registro)
            registros.append(registro)
        db.session.commit()
    except Exception as erro:
        db.session.rollback()
        return _erro(f"Importação cancelada: {erro}", 422)

    return jsonify({"ok": True, "quantidade": len(registros), "registros": [r.to_dict() for r in registros]})


# ============================================================
# BLOCO: API DE REPLICAÇÃO
# ============================================================

@previsao_bp.route("/api/<int:previsao_id>/replicar", methods=["POST"])
@login_required
def replicar(previsao_id):
    """Replica um lançamento para a competência escolhida, sem alterar o original."""
    original = PrevisaoGasto.query.get_or_404(previsao_id)
    if not servico.usuario_pode_setor(current_user, original.setor):
        return _erro("Você não possui permissão para este setor.", 403)

    payload = request.get_json(silent=True) or {}
    competencia = _parse_data(payload.get("competencia"))
    if not competencia:
        return _erro("Informe uma competência válida para a réplica.")

    existente = PrevisaoGasto.query.filter_by(
        setor=original.setor,
        competencia=competencia,
        cia=original.cia,
        fornecedor=original.fornecedor,
        referencia=original.referencia,
        classificacao_nome=original.classificacao_nome,
    ).first()
    if existente and payload.get("acao") not in ("substituir", "criar"):
        return jsonify({
            "ok": False,
            "duplicidade": True,
            "mensagem": "Já existe lançamento semelhante no período de destino.",
            "existente": existente.to_dict(),
        }), 409

    percentual = payload.get("percentual", 0) or 0
    novos = servico.replicar([original], competencia, current_user, percentual)
    return jsonify({"ok": True, "registros": [r.to_dict() for r in novos]})


# ============================================================
# BLOCO: HISTÓRICO E CLASSIFICAÇÕES
# ============================================================

@previsao_bp.route("/api/<int:previsao_id>/historico")
@login_required
def historico(previsao_id):
    """Retorna auditoria de um lançamento, respeitando a permissão do setor."""
    registro = PrevisaoGasto.query.get_or_404(previsao_id)
    if not servico.usuario_pode_setor(current_user, registro.setor):
        return _erro("Acesso negado.", 403)
    eventos = PrevisaoHistorico.query.filter_by(previsao_id=previsao_id).order_by(PrevisaoHistorico.data_hora.desc()).all()
    return jsonify({"ok": True, "historico": [
        {
            "id": e.id,
            "usuario_id": e.usuario_id,
            "campo": e.campo,
            "anterior": e.valor_anterior,
            "novo": e.valor_novo,
            "motivo": e.motivo,
            "data_hora": e.data_hora.isoformat(),
        } for e in eventos
    ]})


@previsao_bp.route("/api/classificacoes", methods=["GET", "POST"])
@login_required
def classificacoes():
    """Lista ou cria classificações; criação é restrita a administradores."""
    if request.method == "GET":
        return jsonify({"ok": True, "classificacoes": [
            {"id": c.id, "nome": c.nome, "ativa": c.ativa}
            for c in PrevisaoClassificacao.query.order_by(PrevisaoClassificacao.nome).all()
        ]})
    if getattr(current_user, "ADM", "N") != "S":
        return _erro("Apenas administradores podem criar classificações.", 403)
    nome = servico.normalizar_texto((request.get_json(silent=True) or {}).get("nome"))
    if not nome:
        return _erro("Informe o nome da classificação.")
    if servico.obter_classificacao(nome):
        return _erro("Classificação já cadastrada.", 409)
    registro = PrevisaoClassificacao(nome=nome, ativa=True)
    db.session.add(registro)
    db.session.commit()
    return jsonify({"ok": True, "classificacao": {"id": registro.id, "nome": registro.nome}}), 201

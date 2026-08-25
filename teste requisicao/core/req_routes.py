# core/req_routes.py
"""
Blueprint do módulo de Requerimentos.

Rotas de tela:
    /requerimento                      -> lista/consulta (nova tela principal do domínio)
    /requerimento/novo                 -> wizard (Abrir Requerimento)
    /requerimento/<id>                 -> detalhes
    /requerimento/<id>/editar          -> wizard em modo edição de rascunho
    /requerimento/<id>/anexo/<anexo_id>-> download autenticado do anexo
    /historico                         -> histórico de requerimentos (tabela + timeline)
    /requerimento/dashboard            -> dashboard de requerimentos
    /requerimento/dados-gerais         -> dados gerais de requerimentos

API (JSON):
    POST   /api/requerimentos
    GET    /api/requerimentos
    GET    /api/requerimentos/<id>
    PUT    /api/requerimentos/<id>
    POST   /api/requerimentos/<id>/enviar
    POST   /api/requerimentos/<id>/cancelar
    POST   /api/requerimentos/<id>/status
    POST   /api/requerimentos/<id>/anexos
    DELETE /api/requerimentos/<id>/anexos/<anexo_id>
    GET    /api/requerimentos/indicadores
    GET    /api/catalogos
    GET    /api/catalogos/produtos?q=
"""

from __future__ import annotations

import os
from datetime import date

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from core import req_catalogos
from core import req_service as servico
from core.req_models import (
    ETAPAS,
    EXTENSOES_ANEXO,
    PRIORIDADES,
    STATUS,
    TIPOS_MOVIMENTO,
    TIPOS_REQUERIMENTO,
    TRANSICOES,
    ReqAnexo,
    Requerimento,
)

req_bp = Blueprint("req", __name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _obter(requerimento_id: int) -> Requerimento:
    requerimento = Requerimento.query.get(requerimento_id)
    if not requerimento:
        abort(404)
    return requerimento


def _erro_json(erro: servico.ErroRequerimento, codigo: int = 400):
    status = 403 if isinstance(erro, servico.AcessoNegado) else codigo
    return jsonify({"ok": False, "erro": erro.mensagem, "campos": erro.campos}), status


def _contexto_dominio() -> dict:
    """Constantes de domínio disponíveis para todos os templates do módulo."""
    return {
        "STATUS": STATUS,
        "PRIORIDADES": PRIORIDADES,
        "TIPOS_REQUERIMENTO": TIPOS_REQUERIMENTO,
        "TIPOS_MOVIMENTO": TIPOS_MOVIMENTO,
        "TRANSICOES": TRANSICOES,
        "ETAPAS": ETAPAS,
        "papel_usuario": servico.papel_do_usuario(current_user),
        "hoje": date.today().isoformat(),
    }


@req_bp.app_context_processor
def _injetar_dominio():
    if not current_user.is_authenticated:
        return {}
    return {"req_status_catalogo": STATUS, "req_prioridades": PRIORIDADES}


# ---------------------------------------------------------------------------
# TELAS
# ---------------------------------------------------------------------------

@req_bp.route("/requerimento")
@login_required
def lista():
    filtros = {
        "q": request.args.get("q", ""),
        "status": request.args.get("status", ""),
        "tipo": request.args.get("tipo", ""),
        "prioridade": request.args.get("prioridade", ""),
        "filial": request.args.get("filial", ""),
        "setor": request.args.get("setor", ""),
        "solicitante": request.args.get("solicitante", ""),
        "data_inicio": request.args.get("data_inicio", ""),
        "data_fim": request.args.get("data_fim", ""),
    }
    ordenar = request.args.get("ordenar", "atualizado_em")
    direcao = request.args.get("direcao", "desc")
    pagina = request.args.get("pagina", 1, type=int)

    try:
        paginacao = servico.listar(current_user, filtros, pagina=pagina,
                                   ordenar=ordenar, direcao=direcao)
    except servico.ErroRequerimento as erro:
        paginacao = servico.listar(current_user, {}, pagina=1)
        filtros["_erro"] = erro.mensagem

    return render_template(
        "requerimentos/lista.html",
        pagina_ativa="requerimentos",
        titulo_pagina="Requerimentos",
        paginacao=paginacao,
        requerimentos=paginacao.items,
        filtros=filtros,
        ordenar=ordenar,
        direcao=direcao,
        opcoes=servico.opcoes_filtro(current_user),
        **_contexto_dominio(),
    )


@req_bp.route("/requerimento/novo")
@login_required
def novo():
    """Abre o wizard. O rascunho só é criado no banco quando o usuário salva,
    evitando lixo de rascunhos vazios."""
    return render_template(
        "requerimentos/wizard.html",
        pagina_ativa="novo",
        titulo_pagina="Novo Requerimento",
        requerimento=None,
        dados_requerimento=None,
        situacao_etapas=None,
        etapa_inicial=1,
        catalogos=req_catalogos.todos(),
        **_contexto_dominio(),
    )


@req_bp.route("/requerimento/<int:requerimento_id>/editar")
@login_required
def editar(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    try:
        servico.exigir_edicao(requerimento, current_user)
    except servico.ErroRequerimento:
        return render_template(
            "requerimentos/detalhe.html",
            pagina_ativa="requerimentos",
            titulo_pagina=requerimento.codigo_exibicao,
            requerimento=requerimento,
            comparativo=servico.comparativo_cotacoes(requerimento),
            aviso="Este requerimento já foi enviado e não pode mais ser editado.",
            **_contexto_dominio(),
        ), 403

    return render_template(
        "requerimentos/wizard.html",
        pagina_ativa="novo",
        titulo_pagina=f"Editar {requerimento.codigo_exibicao}",
        requerimento=requerimento,
        dados_requerimento=requerimento.to_dict(completo=True),
        situacao_etapas=servico.etapas_pendentes(requerimento),
        etapa_inicial=servico.primeira_etapa_incompleta(requerimento),
        catalogos=req_catalogos.todos(),
        **_contexto_dominio(),
    )


@req_bp.route("/requerimento/<int:requerimento_id>")
@login_required
def detalhe(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    try:
        servico.exigir_visualizacao(requerimento, current_user)
    except servico.AcessoNegado as erro:
        abort(403, erro.mensagem)

    return render_template(
        "requerimentos/detalhe.html",
        pagina_ativa="requerimentos",
        titulo_pagina=requerimento.codigo_exibicao,
        requerimento=requerimento,
        comparativo=servico.comparativo_cotacoes(requerimento),
        pode_editar=servico.pode_editar(requerimento, current_user),
        pode_status=servico.pode_alterar_status(current_user),
        proximos_status=[
            {"chave": chave, **STATUS[chave]}
            for chave in TRANSICOES.get(requerimento.status, []) if chave in STATUS
        ],
        **_contexto_dominio(),
    )


@req_bp.route("/historico")
@login_required
def historico():
    filtros = {
        "q": request.args.get("q", ""),
        "status": request.args.get("status", ""),
        "prioridade": request.args.get("prioridade", ""),
        "data_inicio": request.args.get("data_inicio", ""),
        "data_fim": request.args.get("data_fim", ""),
    }
    paginacao = servico.listar(current_user, filtros,
                               pagina=request.args.get("pagina", 1, type=int),
                               por_pagina=12, ordenar="atualizado_em")
    return render_template(
        "requerimentos/historico.html",
        pagina_ativa="historico",
        titulo_pagina="Histórico de Requerimentos",
        paginacao=paginacao,
        requerimentos=paginacao.items,
        filtros=filtros,
        eventos=servico.timeline_geral(current_user, limite=40),
        **_contexto_dominio(),
    )


@req_bp.route("/requerimento/dashboard")
@login_required
def dashboard():
    dados = servico.indicadores(current_user)
    return render_template(
        "requerimentos/dashboard.html",
        pagina_ativa="dashboard",
        titulo_pagina="Dashboard de Requerimentos",
        indicadores=dados,
        recentes=servico.listar(current_user, {}, pagina=1, por_pagina=8).items,
        **_contexto_dominio(),
    )


@req_bp.route("/requerimento/dados-gerais")
@login_required
def dados_gerais():
    return render_template(
        "requerimentos/dados_gerais.html",
        pagina_ativa="dados_gerais",
        titulo_pagina="Dados Gerais de Requerimentos",
        indicadores=servico.indicadores(current_user),
        itens_top=servico.itens_mais_solicitados(current_user),
        fornecedores=servico.fornecedores_cotados(current_user),
        recentes=servico.listar(current_user, {}, pagina=1, por_pagina=10).items,
        catalogos=req_catalogos.todos(),
        **_contexto_dominio(),
    )


@req_bp.route("/requerimento/<int:requerimento_id>/anexo/<int:anexo_id>")
@login_required
def baixar_anexo(requerimento_id: int, anexo_id: int):
    requerimento = _obter(requerimento_id)
    try:
        servico.exigir_visualizacao(requerimento, current_user)
    except servico.AcessoNegado:
        abort(403)

    anexo = ReqAnexo.query.filter_by(id=anexo_id, requerimento_id=requerimento.id).first()
    if not anexo:
        abort(404)

    pasta = os.path.dirname(servico.caminho_anexo(requerimento.id, anexo.nome_arquivo))
    if not os.path.exists(os.path.join(pasta, anexo.nome_arquivo)):
        abort(404)
    return send_from_directory(pasta, anexo.nome_arquivo,
                              as_attachment=True, download_name=anexo.nome_original)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@req_bp.route("/api/requerimentos", methods=["POST"])
@login_required
def api_criar():
    try:
        requerimento = servico.criar_rascunho(current_user)
        payload = request.get_json(silent=True) or {}
        if payload:
            servico.salvar(requerimento, payload, current_user, validacao_completa=False)
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)

    return jsonify({
        "ok": True,
        "id": requerimento.id,
        "requerimento": requerimento.to_dict(completo=True),
        "url_editar": url_for("req.editar", requerimento_id=requerimento.id),
        "url_detalhe": url_for("req.detalhe", requerimento_id=requerimento.id),
    }), 201


@req_bp.route("/api/requerimentos", methods=["GET"])
@login_required
def api_listar():
    filtros = {chave: request.args.get(chave, "") for chave in
               ("q", "status", "tipo", "prioridade", "filial", "setor",
                "solicitante", "data_inicio", "data_fim")}
    try:
        paginacao = servico.listar(
            current_user, filtros,
            pagina=request.args.get("pagina", 1, type=int),
            por_pagina=request.args.get("por_pagina", 15, type=int),
            ordenar=request.args.get("ordenar", "atualizado_em"),
            direcao=request.args.get("direcao", "desc"),
        )
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)

    return jsonify({
        "ok": True,
        "pagina": paginacao.page,
        "paginas": paginacao.pages,
        "total": paginacao.total,
        "itens": [r.to_dict() for r in paginacao.items],
    })


@req_bp.route("/api/requerimentos/<int:requerimento_id>", methods=["GET"])
@login_required
def api_obter(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    try:
        servico.exigir_visualizacao(requerimento, current_user)
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)
    return jsonify({"ok": True, "requerimento": requerimento.to_dict(completo=True)})


@req_bp.route("/api/requerimentos/<int:requerimento_id>", methods=["PUT", "POST"])
@login_required
def api_salvar(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    payload = request.get_json(silent=True) or {}
    try:
        servico.salvar(requerimento, payload, current_user, validacao_completa=False)
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)

    situacao = servico.etapas_pendentes(requerimento)
    return jsonify({
        "ok": True,
        "mensagem": "Rascunho salvo.",
        "requerimento": requerimento.to_dict(completo=True),
        "situacao_etapas": {k: v for k, v in situacao.items() if k != "_erros"},
        "pendencias": situacao["_erros"],
    })


@req_bp.route("/api/requerimentos/<int:requerimento_id>/enviar", methods=["POST"])
@login_required
def api_enviar(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    payload = request.get_json(silent=True) or {}
    try:
        if payload:
            servico.salvar(requerimento, payload, current_user, validacao_completa=False)
        servico.enviar(requerimento, current_user)
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)

    return jsonify({
        "ok": True,
        "mensagem": "Requerimento enviado com sucesso.",
        "codigo": requerimento.codigo,
        "requerimento": requerimento.to_dict(),
        "url_detalhe": url_for("req.detalhe", requerimento_id=requerimento.id),
    })


@req_bp.route("/api/requerimentos/<int:requerimento_id>/cancelar", methods=["POST"])
@login_required
def api_cancelar(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    payload = request.get_json(silent=True) or {}
    try:
        servico.cancelar(requerimento, current_user, payload.get("motivo"))
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)
    return jsonify({"ok": True, "mensagem": "Requerimento cancelado.",
                    "requerimento": requerimento.to_dict()})


@req_bp.route("/api/requerimentos/<int:requerimento_id>/status", methods=["POST"])
@login_required
def api_status(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    payload = request.get_json(silent=True) or {}
    try:
        servico.alterar_status(requerimento, (payload.get("status") or "").upper(),
                               current_user, payload.get("observacao"))
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)
    return jsonify({"ok": True, "mensagem": "Status atualizado.",
                    "requerimento": requerimento.to_dict()})


@req_bp.route("/api/requerimentos/<int:requerimento_id>/anexos", methods=["POST"])
@login_required
def api_anexar(requerimento_id: int):
    requerimento = _obter(requerimento_id)
    arquivos = request.files.getlist("arquivo") or request.files.getlist("arquivos")
    if not arquivos:
        return jsonify({"ok": False, "erro": "Nenhum arquivo recebido."}), 400

    salvos, falhas = [], []
    for arquivo in arquivos:
        try:
            anexo = servico.salvar_anexo(requerimento, arquivo, current_user)
            salvos.append(anexo.to_dict())
        except servico.ErroRequerimento as erro:
            falhas.append({"arquivo": arquivo.filename, "erro": erro.mensagem})

    if not salvos:
        return jsonify({"ok": False, "erro": falhas[0]["erro"] if falhas else "Falha no envio.",
                        "falhas": falhas}), 400
    return jsonify({"ok": True, "anexos": salvos, "falhas": falhas,
                    "mensagem": f"{len(salvos)} anexo(s) enviado(s)."})


@req_bp.route("/api/requerimentos/<int:requerimento_id>/anexos/<int:anexo_id>", methods=["DELETE"])
@login_required
def api_remover_anexo(requerimento_id: int, anexo_id: int):
    requerimento = _obter(requerimento_id)
    try:
        servico.remover_anexo(requerimento, anexo_id, current_user)
    except servico.ErroRequerimento as erro:
        return _erro_json(erro)
    return jsonify({"ok": True, "mensagem": "Anexo removido."})


@req_bp.route("/api/requerimentos/indicadores", methods=["GET"])
@login_required
def api_indicadores():
    return jsonify({"ok": True, "indicadores": servico.indicadores(current_user)})


@req_bp.route("/api/catalogos", methods=["GET"])
@login_required
def api_catalogos():
    return jsonify({"ok": True, "catalogos": req_catalogos.todos(),
                    "extensoes_anexo": sorted(EXTENSOES_ANEXO)})


@req_bp.route("/api/catalogos/produtos", methods=["GET"])
@login_required
def api_produtos():
    resultado = req_catalogos.buscar_produtos(request.args.get("q", ""))
    return jsonify({"ok": True, **resultado})

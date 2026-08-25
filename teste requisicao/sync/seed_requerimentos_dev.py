"""
Semeadura de DADOS FICTÍCIOS de desenvolvimento para o módulo de Requerimentos.

ATENÇÃO
-------
* Este script cria dados de TESTE. Nunca execute em produção.
* Só roda com a variável de ambiente APP_MODO_DEV=1.
* Todos os registros criados recebem a marca "[DEV]" na observação, para que
  seja possível identificá-los e removê-los sem ambiguidade.
* Nada aqui representa dado real do ERP: os cadastros vêm de
  core/req_catalogos.py, que sinaliza a origem (ERP / JSON_INTEGRACAO / MOCK_DEV).

Uso:
    APP_MODO_DEV=1 python sync/seed_requerimentos_dev.py
    APP_MODO_DEV=1 python sync/seed_requerimentos_dev.py --limpar
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

MARCA_DEV = "[DEV]"


def _abortar_se_producao() -> None:
    if os.getenv("APP_MODO_DEV") != "1":
        raise SystemExit(
            "Bloqueado: defina APP_MODO_DEV=1 para semear dados fictícios. "
            "Este script não deve rodar em produção."
        )


def _usuario_dev(db, Usuario):
    """Garante um usuário de testes para vincular os requerimentos."""
    email = "dev.requerimentos@local.test"
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario:
        return usuario

    from werkzeug.security import generate_password_hash

    usuario = Usuario(nome="Usuário DEV Requerimentos", email=email)
    usuario.senha_hash = generate_password_hash("dev12345")
    for campo, valor in (("telefone", "(19) 90000-0000"), ("ATIVO", "S"), ("ADM", "S")):
        if hasattr(usuario, campo):
            setattr(usuario, campo, valor)
    db.session.add(usuario)
    db.session.commit()
    print(f"Usuário de desenvolvimento criado: {email} / senha dev12345")
    return usuario


def limpar(db, modelos) -> None:
    """Remove apenas os requerimentos marcados como DEV."""
    Requerimento = modelos.Requerimento
    alvos = Requerimento.query.filter(
        Requerimento.observacao.like(f"%{MARCA_DEV}%")
    ).all()
    for requerimento in alvos:
        db.session.delete(requerimento)
    db.session.commit()
    print(f"{len(alvos)} requerimento(s) de desenvolvimento removido(s).")


def semear(db, modelos, servico, catalogos) -> None:
    Usuario = _carregar_usuario()
    usuario = _usuario_dev(db, Usuario)

    produtos = catalogos.obter("produtos")["itens"]
    filiais = [f["descricao"] for f in catalogos.obter("filiais")["itens"]] or ["MATRIZ"]
    setores = [s["descricao"] for s in catalogos.obter("setores")["itens"]] or ["ADMINISTRATIVO"]
    fornecedores = [f["descricao"] for f in catalogos.obter("fornecedores")["itens"]] or ["FORNECEDOR TESTE"]
    centros_custo = [c["descricao"] for c in catalogos.obter("centros_custo")["itens"]] or ["ADMINISTRATIVO"]
    centros_gasto = [c["descricao"] for c in catalogos.obter("centros_gasto")["itens"]] or ["GERAL"]
    unidades = [u["descricao"] for u in catalogos.obter("unidades_medida")["itens"]] or ["UN"]

    cenarios = [
        ("COMPRA", "NORMAL", "ENVIADO", 2),
        ("COMPRA", "URGENTE", "EM_ANALISE", 3),
        ("ALMOXARIFADO", "BAIXA", "RASCUNHO", 1),
        ("SERVICO", "ALTA", "AGUARDANDO_APROVACAO", 2),
        ("MANUTENCAO", "NORMAL", "APROVADO", 1),
        ("COMPRA", "ALTA", "EM_COTACAO", 3),
        ("COMPRA", "NORMAL", "ATENDIDO", 2),
        ("OUTRO", "BAIXA", "CANCELADO", 1),
    ]

    criados = 0
    for indice, (tipo, prioridade, status_final, qtd_itens) in enumerate(cenarios):
        referencia = date.today() - timedelta(days=12 * indice)
        itens = []
        for posicao in range(qtd_itens):
            produto = produtos[(indice + posicao) % len(produtos)] if produtos else {
                "codigo": f"DEV{posicao:03d}", "descricao": f"{MARCA_DEV} Item de teste {posicao + 1}"
            }
            itens.append({
                "produto_codigo": produto.get("codigo"),
                "produto_descricao": produto.get("descricao"),
                "descricao_complementar": f"{MARCA_DEV} linha de teste",
                "quantidade": str(2 + posicao * 3),
                "unidade": produto.get("unidade") or unidades[0],
                "valor_referencia": str(Decimal("125.50") + Decimal(posicao * 40)),
                "data_necessidade": (referencia + timedelta(days=10)).isoformat(),
            })

        payload = {
            "geral": {
                "tipo": tipo,
                "prioridade": prioridade,
                "data_referencia": referencia.isoformat(),
                "data_limite": (referencia + timedelta(days=15)).isoformat(),
                "solicitante_nome": usuario.nome,
                "solicitante_email": getattr(usuario, "email", ""),
                "filial": filiais[indice % len(filiais)],
                "setor": setores[indice % len(setores)],
                "responsavel": usuario.nome,
                "centro_custo": centros_custo[indice % len(centros_custo)],
                "centro_gasto": centros_gasto[indice % len(centros_gasto)],
                "categoria": "MATERIAL DE CONSUMO" if tipo == "ALMOXARIFADO" else "COMPRAS",
                "justificativa": (
                    f"{MARCA_DEV} Requerimento de demonstração para validar o fluxo "
                    f"de {tipo.lower()} no ambiente de desenvolvimento."
                ),
                "observacao": f"{MARCA_DEV} registro fictício de desenvolvimento",
                "necessita_cotacao": tipo == "COMPRA",
            },
            "itens": itens,
            "localizacoes": [{
                "filial": filiais[indice % len(filiais)],
                "setor": setores[indice % len(setores)],
                "local": "ALMOXARIFADO CENTRAL",
                "endereco": "Rua de Teste, 100 — Campinas/SP",
                "responsavel_recebimento": usuario.nome,
            }],
            "complementos": [],
            "cotacoes": [],
        }

        if tipo == "COMPRA":
            payload["cotacoes"] = [{
                "fornecedor": fornecedores[posicao % len(fornecedores)],
                "preco_unitario": str(Decimal("130.00") + Decimal(posicao * 25)),
                "quantidade": itens[0]["quantidade"],
                "prazo_entrega_dias": 5 + posicao * 4,
                "condicao_pagamento": "28 DDL",
                "observacao": f"{MARCA_DEV} proposta simulada",
            } for posicao in range(2)]

        requerimento = servico.criar_rascunho(usuario)
        servico.salvar(requerimento, payload, usuario, validacao_completa=False)

        if status_final != "RASCUNHO":
            servico.enviar(requerimento, usuario)
            atual = "ENVIADO"
            caminho = {
                "ENVIADO": [],
                "EM_ANALISE": ["EM_ANALISE"],
                "AGUARDANDO_APROVACAO": ["EM_ANALISE", "AGUARDANDO_APROVACAO"],
                "APROVADO": ["EM_ANALISE", "AGUARDANDO_APROVACAO", "APROVADO"],
                "EM_COTACAO": ["EM_ANALISE", "EM_COTACAO"],
                "ATENDIDO": ["EM_ANALISE", "AGUARDANDO_APROVACAO", "APROVADO", "EM_COMPRA", "ATENDIDO"],
                "CANCELADO": [],
            }[status_final]
            for proximo in caminho:
                servico.alterar_status(requerimento, proximo, usuario,
                                       observacao=f"{MARCA_DEV} transição automática de teste")
                atual = proximo
            if status_final == "CANCELADO":
                servico.cancelar(requerimento, usuario,
                                 motivo=f"{MARCA_DEV} cancelamento de demonstração")

        criados += 1
        print(f"  criado {requerimento.codigo_exibicao} — {status_final}")

    print(f"\n{criados} requerimento(s) de desenvolvimento criados.")


def _carregar_usuario():
    from app import Usuario  # modelo de usuários já existente no projeto (tabela usuarios)
    return Usuario


def principal() -> None:
    _abortar_se_producao()
    os.environ.setdefault("REQ_AUTO_CREATE", "1")

    from app import app
    from core.extensoes import db
    from core import req_models as modelos
    from core import req_service as servico
    from core import req_catalogos as catalogos

    with app.app_context():
        db.create_all()
        if "--limpar" in sys.argv:
            limpar(db, modelos)
            return
        semear(db, modelos, servico, catalogos)


if __name__ == "__main__":
    principal()

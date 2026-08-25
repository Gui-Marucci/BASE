# core/req_catalogos.py
"""
Catálogos auxiliares (produtos, filiais, setores, centros de custo, classes,
almoxarifados, fornecedores).

REGRA (item 41 do escopo): NADA aqui é apresentado como campo real do ERP sem prova.
Ordem de resolução de cada catálogo:

1. `storage/catalogos/<nome>.json`  -> dado oficial gerado pela integração (sync/)
2. `storage/dados_completos.json`   -> reaproveita valores que JÁ existem no JSON de
                                      integração atual (ex.: FILIAL_RESP), quando o
                                      campo estiver presente
3. catálogo de DESENVOLVIMENTO      -> lista mínima marcada com `origem: "MOCK_DEV"`

O frontend recebe sempre `origem` junto do catálogo, e a tela mostra um aviso
"dados de desenvolvimento" quando a origem for MOCK_DEV. Assim o dado real e o
provisório nunca se confundem.

Para plugar o ERP de verdade: gere os arquivos em `storage/catalogos/` no sync
(mesmo formato: lista de objetos {"codigo": ..., "descricao": ...}).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_PATH, "storage")
CATALOGOS_DIR = os.path.join(STORAGE_DIR, "catalogos")

# Campos do JSON de integração atual que podem alimentar catálogos sem inventar dado.
CAMPOS_JSON_INTEGRACAO = {
    "filiais": ["FILIAL_RESP", "FILIAL"],
    "responsaveis": ["RESPONSAVEL_SAC"],
}

MOCK_DEV = {
    "filiais": [
        {"codigo": "01", "descricao": "MATRIZ"},
        {"codigo": "02", "descricao": "FILIAL CAMPINAS"},
        {"codigo": "03", "descricao": "FILIAL SÃO PAULO"},
    ],
    "setores": [
        {"codigo": "ADM", "descricao": "ADMINISTRATIVO"},
        {"codigo": "MAN", "descricao": "MANUTENÇÃO"},
        {"codigo": "OPE", "descricao": "OPERAÇÃO"},
        {"codigo": "TI", "descricao": "TECNOLOGIA"},
        {"codigo": "COM", "descricao": "COMERCIAL"},
    ],
    "unidades_negocio": [
        {"codigo": "UN01", "descricao": "TRANSPORTE"},
        {"codigo": "UN02", "descricao": "ARMAZENAGEM"},
        {"codigo": "UN03", "descricao": "CORPORATIVO"},
    ],
    "centros_gasto": [
        {"codigo": "CG100", "descricao": "OPERACIONAL"},
        {"codigo": "CG200", "descricao": "ADMINISTRATIVO"},
        {"codigo": "CG300", "descricao": "MANUTENÇÃO"},
    ],
    "centros_custo": [
        {"codigo": "CC1001", "descricao": "ADMINISTRAÇÃO GERAL"},
        {"codigo": "CC2001", "descricao": "OFICINA / MANUTENÇÃO"},
        {"codigo": "CC3001", "descricao": "ARMAZÉM"},
        {"codigo": "CC4001", "descricao": "TI"},
    ],
    "classes_sinteticas": [
        {"codigo": "1", "descricao": "MATERIAIS"},
        {"codigo": "2", "descricao": "SERVIÇOS"},
        {"codigo": "3", "descricao": "ATIVO IMOBILIZADO"},
    ],
    "classes_analiticas": [
        {"codigo": "1.01", "descricao": "MATERIAL DE ESCRITÓRIO", "sintetica": "1"},
        {"codigo": "1.02", "descricao": "PEÇAS E COMPONENTES", "sintetica": "1"},
        {"codigo": "1.03", "descricao": "EPI", "sintetica": "1"},
        {"codigo": "2.01", "descricao": "MANUTENÇÃO PREDIAL", "sintetica": "2"},
        {"codigo": "2.02", "descricao": "SERVIÇOS DE TI", "sintetica": "2"},
        {"codigo": "3.01", "descricao": "MÁQUINAS E EQUIPAMENTOS", "sintetica": "3"},
    ],
    "categorias": [
        {"codigo": "MAT", "descricao": "MATERIAL DE CONSUMO"},
        {"codigo": "EPI", "descricao": "EPI / SEGURANÇA"},
        {"codigo": "PEC", "descricao": "PEÇAS"},
        {"codigo": "SER", "descricao": "SERVIÇO"},
        {"codigo": "INF", "descricao": "INFORMÁTICA"},
    ],
    "tipos_requisicao": [
        {"codigo": "NORMAL", "descricao": "NORMAL"},
        {"codigo": "URGENTE", "descricao": "URGENTE"},
        {"codigo": "PROGRAMADA", "descricao": "PROGRAMADA"},
        {"codigo": "REPOSICAO", "descricao": "REPOSIÇÃO DE ESTOQUE"},
    ],
    "almoxarifados": [
        {"codigo": "ALM01", "descricao": "ALMOXARIFADO CENTRAL"},
        {"codigo": "ALM02", "descricao": "ALMOXARIFADO OFICINA"},
        {"codigo": "ALM03", "descricao": "ALMOXARIFADO FILIAL"},
    ],
    "unidades_medida": [
        {"codigo": "UN", "descricao": "UNIDADE"},
        {"codigo": "PC", "descricao": "PEÇA"},
        {"codigo": "CX", "descricao": "CAIXA"},
        {"codigo": "KG", "descricao": "QUILOGRAMA"},
        {"codigo": "L", "descricao": "LITRO"},
        {"codigo": "M", "descricao": "METRO"},
        {"codigo": "M2", "descricao": "METRO QUADRADO"},
        {"codigo": "HR", "descricao": "HORA"},
        {"codigo": "SV", "descricao": "SERVIÇO"},
    ],
    "produtos": [
        {"codigo": "P0001", "descricao": "PAPEL A4 75G - RESMA 500 FOLHAS", "unidade": "CX", "categoria": "MAT"},
        {"codigo": "P0002", "descricao": "CANETA ESFEROGRÁFICA AZUL", "unidade": "UN", "categoria": "MAT"},
        {"codigo": "P0003", "descricao": "TONER IMPRESSORA LASER", "unidade": "UN", "categoria": "INF"},
        {"codigo": "P0004", "descricao": "NOTEBOOK CORPORATIVO 14\"", "unidade": "UN", "categoria": "INF"},
        {"codigo": "P0005", "descricao": "MONITOR 24 POLEGADAS", "unidade": "UN", "categoria": "INF"},
        {"codigo": "P0006", "descricao": "LUVA DE SEGURANÇA PAR", "unidade": "PC", "categoria": "EPI"},
        {"codigo": "P0007", "descricao": "BOTINA DE SEGURANÇA", "unidade": "PC", "categoria": "EPI"},
        {"codigo": "P0008", "descricao": "ÓLEO LUBRIFICANTE 15W40", "unidade": "L", "categoria": "PEC"},
        {"codigo": "P0009", "descricao": "FILTRO DE AR", "unidade": "UN", "categoria": "PEC"},
        {"codigo": "P0010", "descricao": "PNEU 295/80 R22.5", "unidade": "UN", "categoria": "PEC"},
        {"codigo": "S0001", "descricao": "SERVIÇO DE MANUTENÇÃO ELÉTRICA", "unidade": "SV", "categoria": "SER"},
        {"codigo": "S0002", "descricao": "SERVIÇO DE LIMPEZA PREDIAL", "unidade": "SV", "categoria": "SER"},
    ],
    "fornecedores": [
        {"codigo": "F001", "descricao": "DISTRIBUIDORA ALFA LTDA", "documento": "12.345.678/0001-90"},
        {"codigo": "F002", "descricao": "COMERCIAL BETA EIRELI", "documento": "23.456.789/0001-01"},
        {"codigo": "F003", "descricao": "SUPRIMENTOS GAMA S/A", "documento": "34.567.890/0001-12"},
        {"codigo": "F004", "descricao": "TECNOLOGIA DELTA LTDA", "documento": "45.678.901/0001-23"},
    ],
    "condicoes_pagamento": [
        {"codigo": "AV", "descricao": "À VISTA"},
        {"codigo": "28", "descricao": "28 DIAS"},
        {"codigo": "30", "descricao": "30 DIAS"},
        {"codigo": "3060", "descricao": "30/60 DIAS"},
        {"codigo": "306090", "descricao": "30/60/90 DIAS"},
    ],
}


def _ler_json(caminho: str):
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        return None
    except Exception as erro:  # arquivo corrompido não pode derrubar a tela
        print(f"[req_catalogos] Falha ao ler {caminho}: {erro}")
        return None


def _do_json_integracao(nome: str):
    campos = CAMPOS_JSON_INTEGRACAO.get(nome)
    if not campos:
        return None
    dados = _ler_json(os.path.join(STORAGE_DIR, "dados_completos.json"))
    if not isinstance(dados, list) or not dados:
        return None
    valores = set()
    for registro in dados:
        if not isinstance(registro, dict):
            continue
        for campo in campos:
            valor = registro.get(campo)
            if valor and str(valor).strip():
                valores.add(str(valor).strip().upper())
    if not valores:
        return None
    return [{"codigo": v, "descricao": v} for v in sorted(valores)]


@lru_cache(maxsize=64)
def obter(nome: str) -> dict:
    """Retorna {"origem": "...", "itens": [...]} para o catálogo pedido."""
    arquivo = os.path.join(CATALOGOS_DIR, f"{nome}.json")
    oficial = _ler_json(arquivo)
    if isinstance(oficial, list) and oficial:
        return {"origem": "ERP", "itens": oficial}

    integracao = _do_json_integracao(nome)
    if integracao:
        return {"origem": "JSON_INTEGRACAO", "itens": integracao}

    return {"origem": "MOCK_DEV", "itens": MOCK_DEV.get(nome, [])}


def limpar_cache() -> None:
    obter.cache_clear()


def todos() -> dict:
    """Pacote completo usado pelo wizard (1 requisição só)."""
    nomes = [
        "filiais", "setores", "unidades_negocio", "centros_gasto", "centros_custo",
        "classes_sinteticas", "classes_analiticas", "categorias", "tipos_requisicao",
        "almoxarifados", "unidades_medida", "produtos", "fornecedores",
        "condicoes_pagamento", "responsaveis",
    ]
    pacote = {}
    for nome in nomes:
        pacote[nome] = obter(nome)
    return pacote


def buscar_produtos(termo: str, limite: int = 25) -> dict:
    catalogo = obter("produtos")
    termo = (termo or "").strip().upper()
    itens = catalogo["itens"]
    if termo:
        itens = [
            item for item in itens
            if termo in str(item.get("descricao", "")).upper()
            or termo in str(item.get("codigo", "")).upper()
        ]
    return {"origem": catalogo["origem"], "itens": itens[:limite]}

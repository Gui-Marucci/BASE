import os
import json
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
STORAGE_DIR = ROOT_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


def carregar_sql(caminho_relativo: str) -> str:
    caminho_sql = BASE_DIR / caminho_relativo
    return caminho_sql.read_text(encoding="utf-8")


def criar_engine_sqlserver():
    url = URL.create(
        "mssql+pyodbc",
        username=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_RD_PASSWORD"),
        host=os.getenv("DB_SERVER"),
        database=os.getenv("DB_DATABASE"),
        query={
            "driver": os.getenv("DB_DRIVER", "ODBC Driver 13 for SQL Server"),
            "TrustServerCertificate": "yes",
            "Encrypt": "no",
        },
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def normalizar_valor(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def gerar_janelas(data_inicio: date, data_fim: date, dias=15):
    """Gera janelas de N dias com fim exclusivo (sem duplicar)"""
    atual = data_inicio
    while atual < data_fim:
        prox = min(atual + timedelta(days=dias), data_fim)
        yield atual, prox
        atual = prox


def extrair_janela_com_retry(engine, sql_texto, ini, fim, max_tentativas=3):
    params = {"data_inicio": ini.isoformat(), "data_fim": fim.isoformat()}

    for tentativa in range(1, max_tentativas + 1):
        try:
            with engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(text(sql_texto), params)
                colunas = list(result.keys())
                rows = result.fetchall()
                return colunas, rows
        except Exception as e:
            print(f"\n⚠️  Erro na tentativa {tentativa}/{max_tentativas}: {e}")
            if tentativa < max_tentativas:
                print("   Aguardando 5 segundos antes de tentar novamente...")
                time.sleep(5)
            else:
                print(f"   ❌ Falhou após {max_tentativas} tentativas. Pulando janela {ini} → {fim}.")
                return None, []


def main():
    print("--- Extração Incremental (15 dias, Fim Exclusivo) ---\n")
    engine = criar_engine_sqlserver()

    sql_texto = carregar_sql(os.path.join("VIEW", "VW_BASE_550.sql"))

    data_inicio = date(2026, 1, 1)  #*****************************************************************************************************************************************
    data_fim = date.today() + timedelta(days=1)

    arquivo_temp = STORAGE_DIR / "base_temp.jsonl"

    # Se já existir, remove antes de começar
    if arquivo_temp.exists():
        arquivo_temp.unlink()

    total_geral = 0

    # Fase de escrita incremental (gera somente temp)
    with arquivo_temp.open("a", encoding="utf-8") as f_out:
        for ini, fim in gerar_janelas(data_inicio, data_fim, dias=15):
            print(f"Janela: {ini} → {fim} (exclusivo)... ", end="", flush=True)

            colunas, rows = extrair_janela_com_retry(engine, sql_texto, ini, fim)

            if colunas is None:
                continue

            for row in rows:
                obj = {colunas[i]: normalizar_valor(row[i]) for i in range(len(colunas))}
                f_out.write(json.dumps(obj, ensure_ascii=False) + "\n")

            quantidade = len(rows)
            total_geral += quantidade

            print(f"✅ {quantidade} registros (Total: {total_geral})")

    print(f"\n📦 Arquivo temporário: {arquivo_temp.resolve()}")

    # Converte para JSON final e EXCLUI o .jsonl depois
    print("\n🔄 Convertendo para JSON final...")

    dados = []
    with arquivo_temp.open("r", encoding="utf-8") as f:
        for line in f:
            dados.append(json.loads(line.strip()))

    json_final = STORAGE_DIR / "base_dados.json"
    with json_final.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON Final gerado: {json_final.resolve()}")
    print(f"📊 Total final: {len(dados)} registros")

    # Remove o temporário após converter tudo
    print("🧹 Removendo arquivo base_temp.jsonl...")
    try:
        arquivo_temp.unlink()
        print("✔ Arquivo temporário removido com sucesso!")
    except:
        print("⚠ Não foi possível remover o arquivo temporário (verifique permissões).")

    print("\n🎉 Concluído!")


if __name__ == "__main__":
    main()
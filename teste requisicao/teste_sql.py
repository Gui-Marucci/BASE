import pyodbc

SERVIDOR = "localhost,1433"
BANCO = "Prev_Teste"
USUARIO = "sa"
SENHA = "local"

connection_string = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVIDOR};"
    f"DATABASE={BANCO};"
    f"UID={USUARIO};"
    f"PWD={SENHA};"
    "TrustServerCertificate=yes;"
)

try:
    print("Tentando conectar...")

    conexao = pyodbc.connect(connection_string)

    print("CONEXÃO COM SQL SERVER REALIZADA!")

    cursor = conexao.cursor()

    # Teste simples
    cursor.execute("SELECT 1 AS teste")

    resultado = cursor.fetchone()

    if resultado:
        print("Consulta SQL executada com sucesso!")
        print("Resultado:", resultado[0])
    else:
        print("A consulta não retornou dados.")

    # Descobrir o banco atual
    cursor.execute("SELECT DB_NAME()")

    resultado_banco = cursor.fetchone()

    if resultado_banco:
        print("Banco conectado:", resultado_banco[0])

    conexao.close()

    print("Conexão encerrada.")

except Exception as erro:

    print("====================================")
    print("ERRO")
    print("====================================")
    print(erro)
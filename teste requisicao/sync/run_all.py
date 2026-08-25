import subprocess
import sys
import os

def rodar_comando(comando):
    """Executa um comando de sistema e monitora a saída."""
    print(f"\n🚀 Executando: {' '.join(comando)}")
    try:
        # Executa o comando e redireciona a saída para o terminal em tempo real
        resultado = subprocess.run(
            comando, 
            check=True, 
            text=True,
            env=os.environ.copy() # Garante que as variáveis de ambiente passem adiante
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERRO ao executar {comando[2]}:")
        print(f"Código de retorno: {e.returncode}")
        return False
    except Exception as e:
        print(f"\n⚠️ Erro inesperado: {e}")
        return False

def main():
    # Lista de tarefas na sequência exata que você pediu
    tarefas = [
        ["python", "-m", "core.dados_base"],
        ["python", "-m", "core.lista_pos_vei_3S"],
        ["python", "-m", "core.lista_vei_at"],
        ["python", "-m", "core.sync_db_at_3s"]
    ]

    print("="*50)
    print("       INICIANDO SINCRONIZAÇÃO COMPLETA       ")
    print("="*50)

    for i, tarefa in enumerate(tarefas, 1):
        print(f"\nPasso {i}/{len(tarefas)}")
        sucesso = rodar_comando(tarefa)
        
        if not sucesso:
            print("\n⛔ Sincronização interrompida devido a erro no passo anterior.")
            sys.exit(1)

    print("\n" + "="*50)
    print("✨ TODAS AS ETAPAS CONCLUÍDAS COM SUCESSO! ✨")
    print("="*50)

if __name__ == "__main__":
    # Garante que o script consiga enxergar a raiz do projeto para o -m funcionar
    # Adiciona o diretório pai (raiz) ao PYTHONPATH
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(raiz)
    
    main()
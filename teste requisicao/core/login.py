# arquivo para fazer a ponte entre o banco com site 

# bibliotecas 
# Ela faz a comparação do Hash
# arquivo para fazer a ponte entre o banco com site 

from werkzeug.security import check_password_hash
from flask_login import login_user

def validar_e_logar(usuario, senha_digitada):
    # Verifica se o usuário vindo do banco existe
    if usuario and check_password_hash(usuario.senha_hash, senha_digitada):
        login_user(usuario) # Cria a sessão para o current_user funcionar
        return True
    return False





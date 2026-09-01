# Base limpa — Camadas 1–3

## Objetivo

Esta branch é uma reconstrução incremental baseada apenas na camada de autenticação do repositório original. As funcionalidades de negócio anteriores foram descartadas para evitar acoplamento e permitir evolução por camadas.

## Camadas atuais

1. **Index / Login** — autenticação, cadastro e recuperação de senha. Após autenticação válida, o usuário segue para `/inicio`.
2. **Início** — página autenticada deliberadamente vazia; será o ponto de entrada das próximas funcionalidades.
3. **Sidebar** — componente global reutilizável. Alterações feitas neste componente devem refletir em todas as páginas que o incluírem.

## Estrutura

```text
base_app.py
base/
  core/
    auth/
    shell/
    extensions.py
  templates/
    index.html
    inicio.html
    cadastro.html
    recuperar_senha.html
    components/
      sidebar.html
static/
requirements.txt
README.md
```

## Como executar o programa

### 1. Pré-requisitos

É necessário ter instalado:

- Python 3.11 ou superior recomendado;
- Git;
- acesso ao banco de dados utilizado pelo ambiente, quando o modo de desenvolvimento não estiver configurado para SQLite.

### 2. Entrar na pasta da aplicação

No terminal, entre na pasta que contém `base_app.py`:

```bash
cd "teste requisicao"
```

### 3. Criar o ambiente virtual

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação do ambiente, uma alternativa é utilizar o Prompt de Comando:

```cmd
.venv\Scripts\activate.bat
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar as dependências

Com o ambiente virtual ativo:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configurar as variáveis de ambiente

A aplicação utiliza variáveis de ambiente para configurações sensíveis, principalmente chave da aplicação e banco de dados.

Crie um arquivo `.env` na pasta da aplicação **somente se o ambiente local precisar dele**.

Exemplo conceitual:

```env
SECRET_KEY=uma-chave-local
APP_MODO_DEV=1
```

Quando o projeto estiver configurado para desenvolvimento com SQLite, `APP_MODO_DEV=1` permite utilizar a configuração local prevista pela aplicação.

Para ambientes que utilizam MySQL, configure as variáveis de conexão exigidas pelo código da aplicação. **Nunca versione `.env`, senhas, tokens ou credenciais.**

### 6. Executar

A partir da pasta `teste requisicao`, com o ambiente virtual ativo:

```bash
python base_app.py
```

O terminal deverá informar o endereço local disponibilizado pelo servidor. Normalmente, em desenvolvimento Flask, será algo semelhante a:

```text
http://127.0.0.1:5000
```

Abra esse endereço no navegador.

### 7. Fluxo esperado

A primeira tela deve ser o **Index/Login**:

```text
Navegador
   ↓
/index
   ↓
Login válido?
   ├── Não → permanece no fluxo de autenticação
   └── Sim
        ↓
     /inicio
        ↓
   Sidebar global
```

A página `/inicio` permanece propositalmente vazia nesta etapa. A sidebar é o único componente de navegação da aplicação autenticada.

### 8. Desenvolvimento com recarga automática

Para trabalhar durante o desenvolvimento, pode ser utilizado o modo debug do Flask, desde que essa opção esteja prevista/configurada no ponto de entrada da aplicação.

Uma forma equivalente, quando suportada pela configuração atual, é:

```bash
flask --app base_app run --debug
```

Utilize o modo debug somente no ambiente local. Não disponibilize o servidor de desenvolvimento diretamente na internet.

### 9. Verificação rápida após a instalação

Depois de iniciar a aplicação, confirme nesta ordem:

1. `/` ou a rota inicial abre o login;
2. cadastro continua acessível;
3. recuperação de senha continua acessível;
4. credenciais válidas criam a sessão;
5. login válido redireciona para `/inicio`;
6. `/inicio` carrega a sidebar;
7. logout encerra a sessão;
8. acesso direto a `/inicio` sem autenticação retorna ao login.

Se uma dessas etapas falhar, corrija a fundação antes de adicionar uma nova camada.

## Arquivo de configuração e segurança

Não copie credenciais do ambiente original para este projeto. A nova base deve receber suas próprias configurações locais.

Arquivos que não devem ser commitados:

```text
.env
*.db
*.sqlite
*.sqlite3
__pycache__/
.venv/
```

Se o projeto utilizar um banco de desenvolvimento local, ele deve permanecer fora do controle de versão.

## Regra de evolução

Cada nova funcionalidade deve entrar como uma nova camada, sem recuperar templates, rotas ou serviços descartados. Antes de criar código, verificar se existe uma responsabilidade equivalente em uma camada anterior que possa ser reutilizada.

A evolução recomendada é:

```text
Camada 1 — Login / autenticação
        ↓
Camada 2 — Início
        ↓
Camada 3 — Sidebar
        ↓
Camada 4 — próxima funcionalidade
        ↓
Camada 5 — próxima funcionalidade
```

Uma nova camada não deve introduzir dependência desnecessária de funcionalidades futuras ou do projeto legado descartado.

## Comentários

Comentar blocos que expliquem decisões, regras, integrações e cuidados de manutenção. Não adicionar comentários que apenas descrevam literalmente uma instrução.

## Próxima iteração

A próxima camada deve ser construída sobre o fluxo já estabilizado:

**autenticação → início → sidebar**.

O escopo da nova camada deve ser isolado e não deve alterar as responsabilidades das camadas anteriores sem necessidade explícita.
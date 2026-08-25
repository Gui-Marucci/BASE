========================================================================
SUPERSONIC - GESTAO DE REQUERIMENTOS
Passo a passo de execucao
========================================================================

Aplicacao web em Flask (Python) para abertura e acompanhamento de
requerimentos / requisicoes internas, construida sobre o projeto
Supersonic existente (mesmo login, mesmo layout, mesmas rotas antigas).

Documentacao complementar:
  docs/REQUERIMENTOS.md          - documentacao tecnica do modulo
  docs/RELATORIO_TRANSFORMACAO.md - o que foi criado, alterado e preservado


------------------------------------------------------------------------
1. PRE-REQUISITOS
------------------------------------------------------------------------

- Python 3.10 ou superior (verifique com: python --version)
- Acesso ao MySQL corporativo (somente para uso em producao)
- Windows: PowerShell. Linux/Mac: qualquer terminal.


------------------------------------------------------------------------
2. PREPARAR O AMBIENTE (uma vez so)
------------------------------------------------------------------------

Abra o terminal na pasta do projeto (a pasta que contem o app.py).

Windows (PowerShell):

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install pymysql

Linux / Mac:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install pymysql

Observacao: o pymysql e o driver do MySQL e nao esta no requirements.txt
original. Ele so e necessario quando a aplicacao aponta para o banco real.

Se o PowerShell bloquear a ativacao do ambiente virtual, rode uma vez:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass


------------------------------------------------------------------------
3. MODO DE TESTE (sem o MySQL corporativo)  -- RECOMENDADO PARA COMECAR
------------------------------------------------------------------------

Neste modo a aplicacao usa um banco SQLite local em storage/dev.sqlite3.
Nenhum dado do ERP e lido ou gravado.

Windows (PowerShell):

    $env:APP_MODO_DEV="1"
    python sync/seed_requerimentos_dev.py
    python app.py

Linux / Mac:

    export APP_MODO_DEV=1
    python sync/seed_requerimentos_dev.py
    python app.py

O que deve acontecer:

  1) O primeiro comando exibe o aviso "APP_MODO_DEV ativo: usando banco
     SQLite local" e cria 8 requerimentos ficticios, todos marcados com
     [DEV] nas observacoes.
  2) O segundo comando sobe o servidor e imprime:
     Running on http://127.0.0.1:5000

Abra no navegador:

    http://127.0.0.1:5000

Usuario de teste criado pelo seed:

    E-mail: dev.requerimentos@local.test
    Senha:  dev12345

Para apagar apenas os dados ficticios (os marcados com [DEV]):

    python sync/seed_requerimentos_dev.py --limpar

Para parar o servidor: Ctrl + C no terminal.

IMPORTANTE: a variavel APP_MODO_DEV vale somente para a janela de
terminal onde foi definida. Ao abrir um terminal novo, defina de novo.


------------------------------------------------------------------------
4. MODO PRODUCAO (MySQL do ERP)
------------------------------------------------------------------------

4.1 NAO defina APP_MODO_DEV. Configure as variaveis do banco:

    $env:DB_USER="usuario"
    $env:DB_PASSWORD="senha"
    $env:DB_HOST="servidor"
    $env:DB_PORT="3306"
    $env:DB_NAME="base"

    (ou coloque essas chaves em um arquivo .env na raiz do projeto)

4.2 Crie as tabelas do modulo (apenas as tabelas req_*, nada existente
    e alterado):

    mysql -u usuario -p base < migrations/001_requerimentos.sql

4.3 Suba a aplicacao:

    python app.py

Login: use os usuarios que ja existem na tabela usuarios do sistema.


------------------------------------------------------------------------
5. VARIAVEIS DE AMBIENTE DISPONIVEIS
------------------------------------------------------------------------

  DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
      Conexao MySQL. Quando presentes, a aplicacao usa o banco real.

  APP_MODO_DEV=1
      Sem as variaveis acima, usa SQLite local e libera o script de
      dados ficticios. Nunca use em producao.

  REQ_AUTO_CREATE=0
      Desliga a criacao automatica das tabelas req_* na subida.

  REQ_ANEXOS_DIR
      Pasta onde os anexos sao gravados (padrao: storage/anexos).


------------------------------------------------------------------------
6. ROTEIRO RAPIDO DE USO
------------------------------------------------------------------------

  1) Menu lateral > Abrir requerimento.
  2) Etapa 1 (Dados gerais): preencha e clique em "Salvar e continuar".
     O rascunho e criado e ja pode ser retomado depois.
  3) Etapa 2 (Itens): "Adicionar item", busque o produto, informe
     quantidade e valor de referencia.
  4) Etapa 3 (Localizacoes): informe onde entregar / utilizar.
  5) Etapas 4, 5 e 6 (Baixas, Anexos, Cotacoes) sao opcionais.
  6) Etapa 7 (Revisao): confira e clique em "Enviar requerimento".
     O codigo REQ-000001, REQ-000002... e gerado no envio.
  7) Menu > Requerimentos: lista com filtros, ordenacao e paginacao.
  8) Clique em um registro para ver a ficha completa, mudar a situacao
     e acompanhar a linha do tempo.
  9) Menu > Historico, Inicio (dashboard) e Dados gerais mostram os
     indicadores consolidados.

Enquanto o requerimento estiver em Rascunho ele pode ser editado. Depois
de enviado, o acompanhamento e feito por mudanca de situacao; nada e
excluido fisicamente - o que existe e o cancelamento com motivo.


------------------------------------------------------------------------
7. PROBLEMAS COMUNS
------------------------------------------------------------------------

"ModuleNotFoundError: No module named 'flask'"
    O ambiente virtual nao esta ativo. Ative (.venv) e reinstale as
    dependencias.

"No module named 'pymysql'"
    Rode: pip install pymysql

"Configuracao de banco ausente" ao subir
    Faltam as variaveis DB_* (producao) ou o APP_MODO_DEV=1 (teste).

"Address already in use" / porta 5000 ocupada
    Ja existe um servidor rodando. Feche-o (Ctrl + C) ou mude a porta na
    ultima linha do app.py.

Erro 404 de storage/dados_completos.json no console
    Comportamento pre-existente das telas antigas: o arquivo de dados
    nao acompanha o projeto. Nao afeta o modulo de requerimentos.

Campos de filial, setor, centro de custo e produtos com valores
provisorios
    Esperado no modo de desenvolvimento. Esses cadastros ainda nao vem do
    ERP; a propria tela avisa a origem de cada um (aviso amarelo no
    wizard e tabela de origem em Dados gerais). Para integrar, implemente
    as consultas em core/req_catalogos.py ou publique os arquivos em
    storage/catalogos/*.json.


------------------------------------------------------------------------
8. ESTRUTURA DE PASTAS
------------------------------------------------------------------------

  app.py                        aplicacao Flask (login, rotas antigas e
                                registro do modulo de requerimentos)
  core/                         modelos, servicos, catalogos e rotas do
                                modulo de requerimentos
  templates/components/         sidebar, header e macros de interface
  templates/requerimentos/      telas novas (wizard, lista, ficha,
                                historico, dashboard, dados gerais)
  templates/legado/             tela antiga de mapa preservada
  static/css/geral.css          identidade visual original (intocada)
  static/css/requerimentos.css  estilos do modulo
  static/js/req-core.js         toasts, modais e chamadas de API
  static/js/req-wizard.js       logica do wizard de 7 etapas
  migrations/                   DDL das tabelas req_* para MySQL
  sync/                         rotinas de sincronizacao e seed de dev
  storage/                      banco local de dev, anexos e catalogos
  docs/                         documentacao tecnica e relatorio


------------------------------------------------------------------------
9. Correções para patchs futuros
------------------------------------------------------------------------
def dashboard():        

# Relatório da transformação — de Gestão de Frotas para Gestão de Requerimentos

Data: 20/08/2026 · Base: projeto Flask "Supersonic" enviado em `teste-requisicao.zip`

O projeto existente foi **usado como base**, não recriado. Login, identidade
visual, `geral.css`, sidebar, header, rotas e templates originais continuam no
lugar; o módulo de requerimentos foi acrescentado em cima dessa estrutura.

---

## 1. Arquivos criados

| Arquivo | Conteúdo |
|---|---|
| `core/extensoes.py` | instância única do SQLAlchemy, para o app e o blueprint compartilharem |
| `core/req_models.py` | catálogos de domínio (status, prioridades, tipos, etapas) e as 9 tabelas `req_*` |
| `core/req_catalogos.py` | cadastros de apoio com origem declarada (ERP / JSON de integração / mock DEV) |
| `core/req_service.py` | regras de negócio: numeração com lock, salvar, validar, enviar, transições, cancelar, anexos, indicadores |
| `core/req_routes.py` | blueprint `req` com as telas e a API REST |
| `templates/components/sidebar.html` | sidebar componentizada reaproveitando as classes originais |
| `templates/components/header.html` | header como macro (`topbar`), preservando toggle, avatar e dropdown |
| `templates/components/ui.html` | macros: badge de status, badge de prioridade, stepper, campo, área vazia, aviso de origem de dados |
| `templates/requerimentos/base.html` | layout base do módulo (o projeto original não tinha base) |
| `templates/requerimentos/wizard.html` | Abrir Requerimento — 7 etapas |
| `templates/requerimentos/lista.html` | consulta com filtros, ordenação e paginação |
| `templates/requerimentos/detalhe.html` | ficha completa com abas e linha do tempo |
| `templates/requerimentos/historico.html` | encerrados + eventos recentes |
| `templates/requerimentos/dashboard.html` | indicadores de requerimentos |
| `templates/requerimentos/dados_gerais.html` | consolidação e origem dos cadastros |
| `static/css/requerimentos.css` | estilos do módulo, sobre os tokens já existentes |
| `static/js/req-core.js` | toasts, modal, chamadas de API, máscaras, utilidades |
| `static/js/req-wizard.js` | máquina de estados do wizard, linhas dinâmicas, upload, revisão |
| `migrations/001_requerimentos.sql` | DDL MySQL das tabelas `req_*` |
| `sync/seed_requerimentos_dev.py` | dados fictícios de desenvolvimento (exige `APP_MODO_DEV=1`) |
| `docs/REQUERIMENTOS.md` | documentação técnica do módulo |

## 2. Arquivos alterados

**`app.py`**

- `from core.extensoes import db` em vez de instanciar o SQLAlchemy no próprio arquivo
  (a instância é a mesma; nada do modelo `Usuario`/`Usurod` mudou).
- Configuração de banco: continua MySQL quando `DB_USER`/`DB_HOST`/`DB_NAME` existem;
  cai para SQLite local **apenas** com `APP_MODO_DEV=1`; sem nenhuma das opções,
  mantém o erro original de configuração ausente.
- `MAX_CONTENT_LENGTH` de 32 MB, para os anexos.
- Registro do blueprint `req` e criação automática somente das tabelas `req_*`
  (`REQ_AUTO_CREATE`, com try/except para não derrubar a aplicação).
- Filtros de template `moeda`, `data_br` e `data_hora_br`.
- Rota antiga do mapa de veículos preservada em `/legado/requerimento-mapa`
  (endpoint `requerimento_mapa_legado`).
- Novo endpoint chamado `requerimento` em `/abrir-requerimento`, que redireciona
  para o wizard — assim todo `url_for('requerimento')` dos templates legados
  continua funcionando.

**`templates/requerimento.html` → `templates/legado/requerimento_mapa.html`**
Tela antiga de frota/mapa preservada, apenas movida.

**`templates/primeira.html`, `dados_gerais.html`, `comprovante.html`, `perfil_adm.html`, `perfil_atendente.html`**
Um único item novo no menu (“Requerimentos”, apontando para a lista). Nenhum
item existente foi removido ou renomeado.

## 3. O que foi preservado (verificado)

- Login, logout, recuperação de senha, `current_user`, `@login_required` e perfis (`ADM`).
- Todas as rotas e endpoints originais: `painel`, `dados_gerais`, `comprovante`,
  `mapaboard`, `dashboard`, `perfil`, `sair`, `index`, `storage_file`,
  `alterar_vinculo`, `remover_vinculo_direto`, `desativar_usuario`, `recuperar_senha`.
- `static/css/geral.css` intocado; paleta `--azul-noite #394F5A`, `--azul-dia #14B1E7`,
  `--cinza #4D4D4F`, `--bg-body #f4f6f9` reutilizada.
- `static/js/menu-filter.js` (`toggleSidebar`, filtro de menu) continua sendo o
  script de menu, inclusive nas telas novas.
- Nenhuma tabela existente criada, alterada ou removida.

## 4. Como rodar

```bash
pip install -r requirements.txt

# desenvolvimento (SQLite local + dados fictícios)
APP_MODO_DEV=1 python sync/seed_requerimentos_dev.py
APP_MODO_DEV=1 python app.py

# produção (MySQL, como antes)
mysql -u USUARIO -p BASE < migrations/001_requerimentos.sql
python app.py
```

Usuário de testes criado pelo seed: `dev.requerimentos@local.test` / `dev12345`.

## 5. Testes executados

Fluxo exercitado em navegador automatizado (Chromium), com login real:

1. Login → `/requerimento/novo`.
2. Etapa 1 preenchida, "Salvar e continuar" (rascunho criado, URL passa a `/requerimento/<id>/editar`).
3. Etapa 2: item adicionado com quantidade e valor de referência; total recalculado.
4. Etapa 3: localização informada; etapas 4, 5 e 6 percorridas (opcionais).
5. Etapa 7: revisão conferida e envio confirmado no modal → código `REQ-000008`
   gerado e redirecionamento para a ficha.
6. Ficha: abas, indicadores e linha do tempo (CRIADO → ENVIADO) conferidos.
7. Lista, histórico, dashboard e dados gerais verificados com os 10 registros.

Telas revisadas em 1440 px, 820 px e 390 px de largura. Nenhum erro de
JavaScript nas páginas do módulo. O único 404 observado é pré-existente:
`storage/dados_completos.json`, arquivo de dados que não veio no zip e que as
telas legadas consomem.

## 6. Correções feitas durante a revisão visual

- `[hidden]` agora vence o `display` dos botões (o botão "Enviar requerimento"
  aparecia fora da etapa de revisão).
- Abas da ficha passam a quebrar linha (o rótulo "Cotações" era cortado).
- Barras do dashboard remodeladas em grade de três colunas (rótulo, trilha, valor)
  — antes empilhavam e desalinhavam.
- Contraste dos badges de status aumentado (texto escurecido sobre o fundo claro).
- Rascunho identificado como "RASCUNHO Nº 4" em vez de "AUTOMÁTICO".
- Linha do tempo exibe "Situação alterada para Aprovado" em vez de `STATUS_APROVADO`.
- Rascunho não oferece mudança direta de status: o envio passa pela validação do wizard.

## 7. Pontos de atenção

- Os cadastros de apoio ainda não vêm do ERP. A interface **declara** isso em dois
  lugares (aviso no wizard e tabela de origem em Dados Gerais). Para ligar ao ERP,
  implemente as consultas em `core/req_catalogos.py` ou publique os arquivos em
  `storage/catalogos/*.json`.
- A lista de status é um ponto de configuração (`STATUS` e `TRANSICOES` em
  `core/req_models.py`); ajuste conforme o fluxo real antes de usar em produção.
- Anexos são gravados no disco local (`storage/anexos/`). Em ambiente com mais de
  uma instância, troque por armazenamento compartilhado.
- Aprovação por alçada de valor, geração de pedido de compra e notificação por
  e-mail nas transições não foram implementadas — pontos de extensão indicados
  na documentação.

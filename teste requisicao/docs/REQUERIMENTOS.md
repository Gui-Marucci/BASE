# Módulo de Requerimentos — documentação técnica

Sistema web de gestão de requerimentos (requisições/solicitações internas)
construído **sobre o projeto Supersonic existente**: mesma aplicação Flask,
mesmo login, mesma identidade visual, mesmo `geral.css`.

---

## 1. Arquitetura

```
app.py                          # aplicação original + registro do blueprint de requerimentos
core/
  extensoes.py                  # instância única do SQLAlchemy (db), sem app acoplado
  req_models.py                 # catálogos de domínio + tabelas req_*
  req_catalogos.py              # cadastros de apoio (ERP / JSON de integração / mock DEV)
  req_service.py                # regras de negócio (camada de serviço, testável)
  req_routes.py                 # blueprint `req` — telas e API REST
templates/
  components/                   # sidebar, header (macro topbar) e macros de UI
  requerimentos/                # base, wizard, lista, detalhe, historico, dashboard, dados_gerais
  legado/requerimento_mapa.html # tela antiga de mapa/frota preservada
static/css/requerimentos.css    # estilos do módulo (usa os tokens de geral.css)
static/js/req-core.js           # toasts, modal, API, máscaras e utilidades
static/js/req-wizard.js         # máquina de estados do wizard de 7 etapas
migrations/001_requerimentos.sql# DDL MySQL das tabelas req_*
sync/seed_requerimentos_dev.py  # dados FICTÍCIOS de desenvolvimento (bloqueado sem APP_MODO_DEV=1)
```

Camadas: **rota fina → serviço → modelo**. Nenhuma regra de negócio dentro de
template ou de rota; nenhuma query montada por concatenação de string.

## 2. Banco de dados

Todas as tabelas do módulo usam o prefixo `req_`, sem tocar em nenhuma tabela
existente (`usuarios`, `usurod`, etc.).

| Tabela | Função |
|---|---|
| `req_sequencia` | numeração sequencial por série, com lock (`SELECT ... FOR UPDATE`) |
| `req_usuario_papel` | papel do usuário no módulo (SOLICITANTE / ANALISTA / APROVADOR / ADMIN) |
| `req_requerimento` | documento principal (cabeçalho, classificação, status, auditoria) |
| `req_item` | itens solicitados (produto, quantidade, unidade, valor de referência) |
| `req_localizacao` | onde entregar/utilizar cada item |
| `req_complemento` | baixas/complementos (consumo, transferência, atendimento) |
| `req_anexo` | metadados dos arquivos (o binário fica em `storage/anexos/<req_id>/`) |
| `req_cotacao` | propostas de fornecedores, com marcação da vencedora |
| `req_historico` | trilha de auditoria: quem fez o quê, quando, de qual status para qual |

Decisões relevantes:

- **Dinheiro e quantidade** em `NUMERIC(15,2)` / `NUMERIC(15,4)` e `Decimal` no Python — nunca `float`.
- **Nenhuma exclusão física de documento**: requerimento é `CANCELADO` (com motivo,
  autor e data). Linhas filhas (itens, cotações) podem ser removidas apenas enquanto
  o documento é editável.
- **Auditoria** em todas as tabelas de documento: `criado_em/criado_por` e
  `atualizado_em/atualizado_por`, mais o histórico de eventos.
- **Numeração** obtida em `req_sequencia` com lock por série — nunca `MAX(numero)+1`.
- **Transação única** por operação: cabeçalho, itens, localizações, complementos,
  cotações e histórico gravam juntos ou nada é gravado.

Aplicação do DDL em MySQL:

```bash
mysql -u USUARIO -p BASE < migrations/001_requerimentos.sql
```

Em desenvolvimento, `REQ_AUTO_CREATE` (padrão ligado) cria apenas as tabelas
`req_*` na subida da aplicação; nenhuma tabela legada é criada ou alterada.

## 3. Configuração

| Variável | Efeito |
|---|---|
| `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_NAME` | usa MySQL (comportamento de produção, igual ao original) |
| `APP_MODO_DEV=1` | sem variáveis de banco, cai para SQLite em `storage/dev.sqlite3` e libera o seed |
| `REQ_AUTO_CREATE=0` | desliga a criação automática das tabelas `req_*` |
| `REQ_ANEXOS_DIR` | diretório dos anexos (padrão `storage/anexos`) |

Sem nenhuma das opções acima a aplicação continua exigindo as credenciais do
banco, exatamente como antes.

## 4. Status e transições

`RASCUNHO → ENVIADO → EM_ANALISE → AGUARDANDO_APROVACAO → APROVADO → EM_COMPRA → ATENDIDO`,
com desvios para `EM_COTACAO`, `REPROVADO` e `CANCELADO`.

Os status **não são fixos no código das telas**: vivem em `STATUS` e `TRANSICOES`
(`core/req_models.py`). Para adaptar ao fluxo real do ERP, edite esses dois
dicionários — telas, filtros, badges e dashboard passam a refletir a mudança.
Cada status tem `label`, `cor` e `icone`.

## 5. Etapas do wizard

1. **Geral** — tipo, prioridade, datas, solicitante, filial/setor, classificação, justificativa
2. **Itens** — linhas dinâmicas com busca no catálogo, quantidade, unidade, valor de referência
3. **Localizações** — filial, almoxarifado, setor, local, endereço, recebedor
4. **Baixas / complementos** — opcional: movimentos previstos e documentos de origem
5. **Anexos** — upload por arrastar-e-soltar (15 MB por arquivo, extensões permitidas)
6. **Cotações** — propostas por fornecedor, com destaque de menor preço / melhor prazo
7. **Revisão** — conferência final antes do envio

Ações: `Salvar rascunho`, `Salvar e continuar`, `Voltar`, `Enviar requerimento`
e `Cancelar` (com confirmação). O rascunho só é criado no banco quando o usuário
salva, evitando registros vazios.

## 6. Validações

Toda validação existe **nas duas pontas**. O JavaScript apenas antecipa a
mensagem; o servidor decide (`core/req_service.validar`). Obrigatórios para
envio: tipo, solicitante, e-mail válido, filial, setor, centro de custo, data
limite, justificativa (mínimo 10 caracteres), pelo menos um item com quantidade
maior que zero e pelo menos uma localização. Se o requerimento estiver marcado
como "necessita cotação", ao menos uma cotação é exigida. Data limite não pode
ser anterior à data de referência.

## 7. Permissões

Reaproveitam o login existente (`flask_login`, `current_user`, coluna `ADM`).
Papéis do módulo, em `req_usuario_papel` (com fallback pelo campo `ADM`):

| Papel | Pode ver | Pode editar | Pode mudar status |
|---|---|---|---|
| SOLICITANTE | os próprios | os próprios em rascunho | não |
| ANALISTA | todos | rascunhos | sim |
| APROVADOR | todos | rascunhos | sim |
| ADMIN | todos | rascunhos | sim |

A verificação é sempre no servidor, inclusive no escopo das consultas de lista,
dashboard e histórico. Esconder botão não é controle de acesso.

## 8. API REST

| Método | Rota | Função |
|---|---|---|
| POST | `/api/requerimentos` | cria rascunho e grava o payload |
| GET | `/api/requerimentos` | lista paginada (mesmos filtros da tela) |
| GET/PUT | `/api/requerimentos/<id>` | leitura / atualização do rascunho |
| POST | `/api/requerimentos/<id>/enviar` | valida e envia |
| POST | `/api/requerimentos/<id>/status` | aplica transição válida |
| POST | `/api/requerimentos/<id>/cancelar` | cancela com motivo |
| POST/DELETE | `/api/requerimentos/<id>/anexos[/<anexo_id>]` | anexos |
| GET | `/api/requerimentos/indicadores` | números do dashboard |
| GET | `/api/catalogos`, `/api/catalogos/produtos?q=` | cadastros de apoio |

Erros voltam como `{"erro": "mensagem", "campos": {"campo": "mensagem"}}` com
status HTTP adequado (400 validação, 403 permissão, 404 inexistente).

## 9. Cadastros de apoio e honestidade dos dados

`core/req_catalogos.py` resolve cada cadastro em três origens, nesta ordem:

1. **ERP** — tabela/consulta real, quando configurada;
2. **JSON_INTEGRACAO** — arquivo em `storage/catalogos/<nome>.json`, alimentado por rotina de integração;
3. **MOCK_DEV** — valores provisórios de desenvolvimento.

A origem é exibida na interface: o wizard mostra um aviso amarelo listando quais
cadastros ainda estão em modo desenvolvimento, e a página **Dados Gerais** tem
uma tabela com a origem de cada um. Nenhum dado provisório é apresentado como
se fosse dado real do ERP.

## 10. Dados de desenvolvimento

```bash
APP_MODO_DEV=1 python sync/seed_requerimentos_dev.py            # cria 8 requerimentos fictícios
APP_MODO_DEV=1 python sync/seed_requerimentos_dev.py --limpar   # remove só os marcados [DEV]
```

Todo registro criado leva a marca `[DEV]` na observação. O script se recusa a
rodar sem `APP_MODO_DEV=1`.

## 11. O que ficou pendente de integração

- Consultas reais aos cadastros do ERP (filiais, setores, centros, produtos, fornecedores).
- Regras de aprovação por alçada/valor, se existirem no ERP.
- Reflexo em estoque/compras (geração de pedido) na etapa "Em compra".
- Notificação por e-mail nas transições (o projeto já tem `flask_mail` configurado).

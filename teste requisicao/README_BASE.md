# BASE — Arquitetura incremental por camadas

## Objetivo

Esta pasta contém uma aplicação-base nova construída a partir das referências do repositório `BASE`, mas sem reaproveitar a arquitetura funcional do projeto legado.

A regra desta base é simples: **cada camada possui uma responsabilidade pequena, explícita e substituível**.

O projeto legado continua existindo ao lado dela e não deve ser alterado para implementar as próximas camadas.

## Estado atual

```text
Camada 1 — Index / Login       ✅
Camada 2 — Início              ✅
Camada 3 — Sidebar global      ✅
Camada 4+ — futuras            ⏳
```

### Camada 1 — Index / Login

Responsável por:

- login;
- validação de senha;
- compatibilidade com hashes legados;
- cadastro;
- solicitação de recuperação;
- logout;
- criação/manutenção da sessão.

Após autenticação válida, o destino é sempre:

```text
/inicio
```

A Camada 1 não conhece módulos de negócio.

### Camada 2 — Início

A página é intencionalmente vazia.

Ela existe como superfície estável para receber os próximos módulos. Não adicionar regras de negócio aqui.

### Camada 3 — Sidebar

A sidebar está em:

```text
templates/components/sidebar.html
```

Ela é um componente global. As páginas futuras devem incluí-la em vez de copiar seu HTML.

Uma alteração neste arquivo deve refletir automaticamente em todas as páginas que o utilizarem.

---

## Estrutura

```text
base_app.py
base/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── extensions.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── routes.py
│   └── shell/
│       ├── __init__.py
│       └── routes.py
└── templates/
    ├── index.html
    ├── cadastro.html
    ├── recuperar_senha.html
    ├── inicio.html
    └── components/
        └── sidebar.html

static/css/base.css
```

## Como executar

Entre na pasta `teste requisicao` e execute:

```bash
python base_app.py
```

A aplicação base utiliza a porta `5001` por padrão para não disputar a porta da aplicação legada.

### Desenvolvimento

Use:

```text
APP_MODO_DEV=1
```

Nesse modo é criado um banco SQLite isolado:

```text
storage/base_dev.sqlite3
```

Esse banco não deve ser confundido com o banco de produção.

### Produção

Defina as mesmas variáveis de conexão utilizadas pelo ambiente corporativo:

```text
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT
DB_NAME
```

O `.env` não deve ser commitado.

---

## Regras para futuras iterações

### 1. Não aumentar a responsabilidade da Camada 1

Login deve continuar sendo login.

Não adicionar dashboards, requisições, previsões, relatórios ou regras de negócio em `base/core/auth`.

### 2. Não colocar módulos na página Início

A Camada 2 deve funcionar como shell de entrada.

Quando uma nova funcionalidade for criada, ela deve receber sua própria rota, serviço e template.

### 3. Não duplicar a Sidebar

Nunca copie:

```html
<aside class="base-sidebar">...</aside>
```

Para outra página.

Use:

```jinja2
{% include 'components/sidebar.html' %}
```

### 4. Uma funcionalidade = um módulo

Preferir:

```text
core/
└── previsao/
    ├── models.py
    ├── services.py
    ├── routes.py
    └── __init__.py
```

em vez de adicionar centenas de linhas a `base_app.py`.

### 5. Rotas não devem concentrar regras complexas

Fluxo recomendado:

```text
rota
 ↓
serviço
 ↓
modelo / banco
```

A rota deve cuidar do HTTP e o serviço deve cuidar da regra de negócio.

### 6. Comentários

Todo bloco relevante deve explicar contexto, regra, integração ou decisão.

Evitar comentários óbvios como:

```python
# soma dois números
```

Preferir:

```python
# Consolida o valor filtrado para alimentar o indicador financeiro.
```

### 7. Iterações pequenas

Cada nova camada deve ser implementada e validada antes da próxima.

Fluxo recomendado:

```text
Planejar
→ criar estrutura mínima
→ testar
→ integrar
→ documentar
→ próximo ciclo
```

---

## Próxima camada

Quando a Camada 3 estiver validada, a próxima funcionalidade deve ser criada como uma camada independente.

Exemplo:

```text
Camada 4 — Requisições
```

Ela deverá possuir sua própria área, suas rotas e suas regras, mas poderá utilizar o shell global da Camada 3.

O objetivo é que uma alteração na sidebar não exija alterar cada módulo individualmente.

---

## Regra arquitetural principal

> **As camadas dependem da infraestrutura comum; nunca devem depender diretamente umas das regras internas das outras.**

Isso mantém o projeto fácil de ler, testar, modificar e expandir.

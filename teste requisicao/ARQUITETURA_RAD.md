# Arquitetura RAD — MVP de Requisições

<!-- ============================================================
DOCUMENTAÇÃO: ARQUITETURA RAD
OBJETIVO: registrar as decisões estruturais para facilitar iterações curtas.
============================================================ -->

## Escopo do primeiro ciclo

A branch `refactor/rad-base` reduz a aplicação autenticada a três superfícies:

1. **Início** — shell com sidebar e área central vazia.
2. **Requisições** — consulta e abertura usando o domínio `req_*` existente.
3. **Perfil** — perfil do usuário ou administração, conforme permissão.

O login, cadastro, recuperação de senha, logout e recuperação de credenciais continuam no fluxo existente.

## Princípios RAD aplicados

### 1. Shell estável

`templates/rad/base.html` concentra a estrutura comum. Uma nova funcionalidade deve entrar como bloco de conteúdo, sem duplicar sidebar, cabeçalho ou carregamento de dependências.

### 2. Domínio reutilizado

O módulo de Requisições continua utilizando `req_routes.py`, `req_service.py` e `req_models.py`. A mudança é principalmente de apresentação e composição, não de regra de negócio.

### 3. Ciclos pequenos

Cada nova funcionalidade futura deve poder ser adicionada como uma fatia vertical pequena:

`rota → serviço → template → interação → validação`

### 4. Baixo acoplamento

A navegação aponta para endpoints existentes. Isso permite refatorar a interface sem reconstruir autenticação ou persistência.

### 5. Comentários com contexto

Comentários devem registrar decisões, integrações, regras e pontos de manutenção. Não devem narrar instruções óbvias.

## Estrutura alvo

```text
teste requisicao/
├── app.py                     # bootstrap e autenticação existentes
├── core/
│   ├── req_models.py          # domínio de requisições existente
│   ├── req_routes.py          # endpoints existentes
│   └── req_service.py         # regras existentes
├── templates/
│   ├── rad/
│   │   └── base.html          # shell RAD
│   ├── components/
│   │   └── sidebar.html       # navegação mínima do MVP
│   ├── requerimentos/
│   │   ├── dashboard.html     # Início vazio
│   │   └── lista.html          # Requisições
│   ├── perfil_adm.html         # Perfil administrativo
│   └── perfil_atendente.html  # Perfil individual
└── static/
    ├── css/rad.css             # camada visual incremental
    └── js/rad.js               # interações compartilhadas
```

## O que deliberadamente não faz parte deste ciclo

- Dashboard operacional antigo.
- Dados Gerais.
- Comprovantes.
- Histórico como item de navegação.
- Mapa operacional.
- Previsão de gastos.

Essas funcionalidades não são apagadas do repositório nesta etapa; deixam de fazer parte da navegação principal do MVP. Isso permite recuperar ou reintroduzir um domínio em um ciclo futuro sem comprometer login e persistência.

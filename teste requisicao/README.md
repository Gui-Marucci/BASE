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

## Regra de evolução

Cada nova funcionalidade deve entrar como uma nova camada, sem recuperar templates, rotas ou serviços descartados. Antes de criar código, verificar se existe uma responsabilidade equivalente em uma camada anterior que possa ser reutilizada.

## Comentários

Comentar blocos que expliquem decisões, regras, integrações e cuidados de manutenção. Não adicionar comentários que apenas descrevam literalmente uma instrução.

## Próxima iteração

A próxima camada deve ser construída sobre o fluxo já estabilizado: autenticação → início → sidebar. O escopo da nova camada deve ser isolado e não deve alterar as responsabilidades das camadas anteriores sem necessidade explícita.

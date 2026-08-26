# Arquitetura RAD — primeira iteração

## Objetivo

Esta branch reduz a experiência autenticada ao núcleo **Início → Requisições → Perfil**.
A mudança é incremental: o backend legado permanece disponível onde necessário,
enquanto a interface principal passa a utilizar uma casca pequena e reutilizável.

## Princípios

- ciclos curtos e verificáveis;
- baixo acoplamento entre apresentação e regras de negócio;
- reaproveitamento de autenticação, usuários, permissões e domínio de requisições;
- mudanças visuais concentradas no shell;
- funcionalidades futuras adicionadas como módulos independentes;
- compatibilidade com o fluxo existente antes de qualquer otimização estrutural maior.

## Camadas atuais

```text
Flask app
  ├── autenticação/sessão existente
  ├── req_bp
  │    ├── routes → recebe HTTP e delega
  │    ├── req_service → regras de negócio
  │    └── req_models → persistência
  └── templates
       └── requerimentos/base.html → shell RAD
            ├── components/sidebar.html
            ├── components/header.html
            └── páginas do domínio
```

## Decisão de primeira iteração

A rota `req.dashboard` foi mantida como endpoint inicial autenticado, mas seu
conteúdo deixou de ser o dashboard operacional. Isso evita alterar o fluxo de
login enquanto transforma a página em uma superfície vazia para RAD.

O menu não expõe dados gerais, comprovantes, histórico, mapas ou outras telas
legadas. Essas rotas não são apagadas nesta etapa porque podem possuir dependências
internas ou servir de compatibilidade.

## Próximos ciclos

1. estabilizar shell e perfil;
2. reduzir a tela de requisição ao fluxo mínimo de criação;
3. revisar API e validações do domínio;
4. testar rascunho → revisão → envio → acompanhamento;
5. somente depois extrair novas subcamadas quando houver necessidade real.

## Regra de manutenção

Não introduzir abstrações apenas para cumprir um padrão arquitetural. Uma nova
camada deve existir quando resolver um acoplamento, permitir teste isolado ou
facilitar uma iteração prevista.

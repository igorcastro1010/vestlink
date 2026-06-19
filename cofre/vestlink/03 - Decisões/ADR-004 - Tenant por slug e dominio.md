---
tipo: decisao
status: ativo
decisao: aceita
revisado_em: 2026-06-15
fontes:
  - ../../../loja/middleware.py
  - ../../../config/urls_tenant.py
  - ../../../loja/apps.py
---

# ADR-004 - Tenant por slug e domínio

> [!summary] TL;DR
> Toda loja possui slug e pode ser resolvida por rota, subdomínio ou domínio
> próprio. No host da loja, URLs públicas deixam de carregar o slug.

## Decisão

`TenantMiddleware` identifica a loja pelo host e troca o URLConf. Um ajuste
global em `reverse()` remove o slug de rotas públicas dentro do tenant.

## Consequências

- Link curto funciona mesmo sem domínio próprio.
- Domínios precisam apontar para a Vercel e estar autorizados.
- O monkeypatch global de `django.urls.reverse` aumenta o risco de efeitos
  colaterais em upgrades e testes.

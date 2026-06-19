---
tipo: decisao
status: ativo
decisao: aceita
revisado_em: 2026-06-15
fontes:
  - ../../../api/index.py
  - ../../../vercel.json
---

# ADR-001 - Django monolítico na Vercel

> [!summary] TL;DR
> Manter um único aplicativo Django server-rendered reduz complexidade enquanto
> produto e operação ainda mudam rapidamente.

## Decisão

Usar Django com templates, uma aplicação `loja` e uma função WSGI na Vercel.

## Consequências

- Desenvolvimento e deploy simples para o estágio atual.
- Regras e UI estão fortemente concentradas em `loja/views.py` e templates.
- Runtime serverless exige banco, mídia e cache persistentes externos.
- Crescimento pode exigir divisão das views e serviços, não necessariamente
  criação precoce de microsserviços.

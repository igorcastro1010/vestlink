---
name: qa-smoke-test
description: Use to run quick VestLink smoke checks after changes: Django check, key pages, auth-adjacent flows, catalog display, forms rendering, static assets, and console errors.
---

# QA Smoke Test

## Objetivo
Confirmar que o basico continua funcionando apos mudancas.

## Quando Usar
Use antes de finalizar alteracoes em UI, templates, CSS, JS ou configuracao.

## Checklist
- Rodar `python manage.py check`.
- Abrir paginas principais no local.
- Conferir assets, console e erros visuais.
- Testar ao menos um fluxo afetado.

## Regras
- Nao executar acoes destrutivas.
- Nao criar dados reais desnecessarios.
- Relatar testes que nao puderam rodar.

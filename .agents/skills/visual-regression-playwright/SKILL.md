---
name: visual-regression-playwright
description: Use to verify VestLink visual changes with Playwright or browser screenshots across key pages, desktop/mobile viewports, and light/dark themes.
---

# Visual Regression Playwright

## Objetivo
Validar visualmente mudancas de UI antes de entregar.

## Quando Usar
Use apos alteracoes visuais em landing, login, cadastro, painel ou catalogo.

## Checklist
- Abrir paginas principais no servidor local.
- Capturar desktop e mobile quando relevante.
- Alternar light/dark quando a tela suportar.
- Procurar texto apagado, overlap, overflow e console errors.

## Regras
- Nao usar screenshots como substituto de teste funcional basico.
- Registrar achados de forma objetiva.
- Nao alterar app durante verificacao sem necessidade.

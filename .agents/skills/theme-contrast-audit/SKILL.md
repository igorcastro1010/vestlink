---
name: theme-contrast-audit
description: Use to audit and fix VestLink light and dark mode contrast for text, links, buttons, badges, cards, inputs, placeholders, tables, menus, and status states.
---

# Theme Contrast Audit

## Objetivo
Garantir leitura clara no modo claro e escuro.

## Quando Usar
Use quando textos estiverem apagados, componentes sumirem no tema ou novas cores forem adicionadas.

## Checklist
- Mapear telas afetadas e tokens usados.
- Verificar texto normal, titulo, label, placeholder e link.
- Verificar hover, focus, disabled, erro, sucesso e alerta.
- Testar visualmente light e dark.

## Regras
- Usar variaveis/tokens para pares light/dark.
- Nao resolver com cor fixa que funcione em so um tema.
- Nao tocar em logica, banco, auth ou rotas.

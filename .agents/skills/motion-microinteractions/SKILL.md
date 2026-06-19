---
name: motion-microinteractions
description: Use to add or refine VestLink CSS/JS microinteractions, hover/focus feedback, subtle animations, loading states, and motion that improves clarity without adding heavy dependencies.
---

# Motion Microinteractions

## Objetivo
Adicionar movimento leve que ajude a experiencia sem distrair.

## Quando Usar
Use em hover, foco, entrada suave, feedback de botao, abas, cards e CTAs.

## Checklist
- Preferir CSS transitions/animations existentes.
- Respeitar `prefers-reduced-motion`.
- Manter performance e evitar layout shift.
- Conferir light/dark e mobile.

## Regras
- Nao usar Framer Motion se o stack nao suportar React.
- Movimento deve ter proposito funcional.
- Nao alterar logica, rotas ou dados.

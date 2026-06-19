---
name: security-review
description: Use to review VestLink security risks in Django templates, forms, auth-adjacent code, external integrations, secrets handling, permissions, destructive actions, and user-generated content.
---

# Security Review

## Objetivo
Identificar riscos de seguranca sem quebrar o produto.

## Quando Usar
Use em formularios, login/cadastro, exclusoes, upload, links externos e permissoes.

## Checklist
- Verificar CSRF, auth, permissao e validacao.
- Procurar segredo exposto ou dado sensivel.
- Conferir acoes destrutivas com confirmacao.
- Avaliar XSS e conteudo de usuario.

## Regras
- Nao alterar auth/banco sem pedido explicito.
- Nao registrar segredos no cofre ou resposta.
- Priorizar riscos reais e reproduziveis.

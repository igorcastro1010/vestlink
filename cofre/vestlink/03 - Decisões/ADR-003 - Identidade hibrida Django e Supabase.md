---
tipo: decisao
status: ativo
decisao: aceita
revisado_em: 2026-06-15
fontes:
  - ../../../loja/supabase_auth.py
  - ../../../loja/views.py
---

# ADR-003 - Identidade híbrida Django e Supabase

> [!summary] TL;DR
> Supabase prova a identidade externa; Django mantém usuário, permissões,
> relações e sessão da aplicação.

## Decisão

Após confirmação de e-mail ou Google OAuth, validar o token Supabase no servidor,
localizar/criar um `User` Django e abrir a sessão Django.

## Consequências

- Relações existentes continuam usando `AUTH_USER_MODEL`.
- É obrigatório evitar usuários duplicados por e-mail.
- Usuários Google recebem senha inutilizável.
- Mudanças de e-mail e exclusão exigem estratégia de sincronização entre os
  dois sistemas.

## Relacionados

- [[fluxos-principais]]
- [[integracoes]]
- [[modelo-de-dados]]
- [[ADR-002 - Supabase como backend principal]]
- [[gotchas-de-producao]]
- [[dividas-abertas]]

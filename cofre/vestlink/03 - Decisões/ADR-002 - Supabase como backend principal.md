---
tipo: decisao
status: ativo
decisao: aceita
revisado_em: 2026-06-15
fontes:
  - ../../../config/settings.py
  - ../../../loja/storage.py
  - ../../../loja/supabase_auth.py
---

# ADR-002 - Supabase como backend principal

> [!summary] TL;DR
> Produção deve usar somente Supabase para PostgreSQL, Auth e Storage. SQLite é
> fallback local; S3 permanece compatibilidade opcional, não direção principal.

## Motivo

Centralizar dados persistentes evita conflito entre provedores e atende ao
runtime stateless da Vercel.

## Consequências

- Conexão deve usar pooler adequado a serverless.
- Service role é necessária para operações de Storage no servidor.
- Configuração Supabase é parte crítica de deploy e recuperação.
- Código de fallback legado deve ser tratado como dívida, não como arquitetura
  de produção recomendada.

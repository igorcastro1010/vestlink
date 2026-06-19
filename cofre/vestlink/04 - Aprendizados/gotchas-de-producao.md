---
tipo: aprendizado
status: ativo
revisado_em: 2026-06-15
fontes:
  - ../../../config/settings.py
  - ../../../README.md
  - ../../../loja/middleware.py
---

# Gotchas de produção

> [!summary] TL;DR
> Os problemas mais prováveis são configuração incompleta de serviço externo,
> persistência local em serverless, callback incorreto e cache por processo.

- **Vercel é stateless:** não confiar em SQLite nem em `media/` local.
- **Pooler Supabase:** manter conexões curtas; `CONN_MAX_AGE=0` é intencional.
- **Auth:** callback deve estar autorizado no Supabase e no Google.
- **Google:** provider precisa estar habilitado e app OAuth em produção.
- **E-mail:** backend de console não envia mensagens reais.
- **Storage:** uploads falham se bucket/chave não estiverem corretos.
- **Cache local:** `LocMemCache` não é compartilhado entre funções Vercel.
- **Webhook:** aprovação depende de consulta ao Mercado Pago.
- **Domínio próprio:** host principal não deve ser confundido com tenant.
- **Assinatura:** catálogos vencidos são bloqueados; cron atualiza trials.
- **Encoding:** já houve texto mojibake em fontes; editar sempre em UTF-8.
- **Deploy:** mudanças locais não publicam até `vercel --prod`.

## Relacionados

- [[integracoes]] detalha os serviços onde esses problemas aparecem.
- [[arquitetura-do-sistema]] explica o runtime serverless e os adaptadores.
- [[fluxos-principais]] mostra callbacks, webhook, cron, e-mail e WhatsApp em uso.
- [[ADR-001 - Django monolitico na Vercel]] contextualiza a decisão de deploy.
- [[ADR-002 - Supabase como backend principal]] contextualiza banco, Auth e Storage.
- [[ADR-004 - Tenant por slug e dominio]] contextualiza host, tenant e domínio próprio.
- [[dividas-abertas]] transforma gotchas em trabalho pendente.

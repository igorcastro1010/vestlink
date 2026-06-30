---
tipo: arquitetura
status: ativo
revisado_em: 2026-06-29
fontes:
  - ../../../config/settings.py
  - ../../../.env.example
  - ../../../loja/supabase_auth.py
  - ../../../loja/storage.py
  - ../../../loja/payments.py
  - ../../../loja/email_backends.py
---

# Integrações

> [!summary] TL;DR
> Supabase é o backend persistente principal; Vercel hospeda; Abacate Pay cobra;
> Resend/SMTP envia e-mail; Google autentica através do Supabase.

| Serviço | Responsabilidade | Configuração principal |
|---|---|---|
| Vercel | Deploy e função Python | `.vercel/project.json`, `vercel.json` |
| Supabase Postgres | Banco de produção | `SUPABASE_DATABASE_URL` |
| Supabase Auth | Confirmação de e-mail e OAuth | `SUPABASE_URL`, chave pública |
| Supabase Storage | Logos, banners e produtos | bucket e service role |
| Google OAuth | Login social | provider configurado no Supabase |
| Abacate Pay | Pagamento Premium por checkout hospedado | `ABACATE_PAY_API_KEY`, `ABACATE_PAY_WEBHOOK_SECRET`, `ABACATE_PAY_WEBHOOK_URL`, `ABACATE_PAY_RETURN_URL` e `ABACATE_PAY_PREMIUM_PRODUCT_ID` |
| Resend/SMTP | E-mails transacionais | `RESEND_API_KEY` e `RESEND_FROM_EMAIL` (Pendentes na Vercel) |
| Redis | Cache compartilhado opcional | `REDIS_URL` |
| Sentry | Erros e tracing opcionais | `SENTRY_DSN`, `SENTRY_SEND_DEFAULT_PII` |
| WhatsApp | Destino de pedidos | telefone da loja e URL externa |

## Invariantes

- Nunca guardar segredos no cofre ou no Git.
- Supabase Auth e usuário Django são identidades sincronizadas, não substitutas.
- URLs de callback devem existir tanto no código quanto na allow-list Supabase.
- Webhook de pagamento não deve confiar apenas nos dados enviados pelo cliente; quando `ABACATE_PAY_WEBHOOK_SECRET` existir, validar secret/assinatura antes de processar.
- Sentry não envia PII por padrão; `SENTRY_SEND_DEFAULT_PII` precisa ser ativado explicitamente.
- Filesystem local serve apenas para desenvolvimento.

## Relacionados

- [[arquitetura-do-sistema]] mostra onde cada serviço entra no monólito.
- [[fluxos-principais]] descreve como Supabase, Google, Abacate Pay, e-mail e WhatsApp participam das jornadas.
- [[ADR-002 - Supabase como backend principal]] registra a decisão sobre PostgreSQL, Auth e Storage.
- [[ADR-003 - Identidade hibrida Django e Supabase]] detalha a relação entre Supabase Auth e Django.
- [[gotchas-de-producao]] lista falhas comuns de ambiente, callback, storage, e-mail e webhook.
- [[dividas-abertas]] acompanha riscos e melhorias pendentes dessas integrações.

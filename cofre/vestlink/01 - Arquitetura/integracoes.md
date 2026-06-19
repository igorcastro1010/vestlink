---
tipo: arquitetura
status: ativo
revisado_em: 2026-06-16
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
> Supabase é o backend persistente principal; Vercel hospeda; Mercado Pago cobra;
> Resend/SMTP envia e-mail; Google autentica através do Supabase.

| Serviço | Responsabilidade | Configuração principal |
|---|---|---|
| Vercel | Deploy e função Python | `.vercel/project.json`, `vercel.json` |
| Supabase Postgres | Banco de produção | `SUPABASE_DATABASE_URL` |
| Supabase Auth | Confirmação de e-mail e OAuth | `SUPABASE_URL`, chave pública |
| Supabase Storage | Logos, banners e produtos | bucket e service role |
| Google OAuth | Login social | provider configurado no Supabase |
| Mercado Pago | Checkout Premium | access token e webhook |
| Resend/SMTP | E-mails transacionais | chave/API ou credenciais SMTP |
| Redis | Cache compartilhado opcional | `REDIS_URL` |
| Sentry | Erros e tracing opcionais | `SENTRY_DSN`, `SENTRY_SEND_DEFAULT_PII` |
| WhatsApp | Destino de pedidos | telefone da loja e URL externa |

## Invariantes

- Nunca guardar segredos no cofre ou no Git.
- Supabase Auth e usuário Django são identidades sincronizadas, não substitutas.
- URLs de callback devem existir tanto no código quanto na allow-list Supabase.
- Webhook de pagamento não deve confiar apenas nos dados enviados pelo cliente.
- Sentry não envia PII por padrão; `SENTRY_SEND_DEFAULT_PII` precisa ser ativado explicitamente.
- Filesystem local serve apenas para desenvolvimento.

---
tipo: divida
status: ativo
prioridade: alta
revisado_em: 2026-06-21
fontes:
  - ../../../config/settings.py
  - ../../../loja/apps.py
  - ../../../loja/views.py
  - ../../../loja/services/
  - ../../../README.md
---

# Dívidas abertas

> [!summary] TL;DR
> Antes de escalar comercialmente, priorizar revisão jurídica, segurança fina,
> observabilidade e redução do acoplamento em views.

| Prioridade | Dívida | Risco / próximo passo |
|---|---|---|
| Alta | Configuração de e-mail transacional (Resend) | `RESEND_API_KEY` e `RESEND_FROM_EMAIL` pendentes na Vercel para habilitar confirmação de cadastro em prod. |
| Alta | Revisão jurídica dos Termos e Privacidade | Textos base e aceite versionado existem; falta validação com profissional jurídico. |
| Alta | Direitos LGPD operacionais | Leads antigos são anonimizados; ainda faltam fluxo de exportação/exclusão por titular e canal formal. |
| Alta | Assinatura real do webhook Mercado Pago e Variáveis | `MERCADO_PAGO_ACCESS_TOKEN` e `MERCADO_PAGO_USE_SANDBOX` ausentes na Vercel (default atual: sandbox; checkout real desativado). Webhook consulta a API oficial mas não valida `X-Signature`. Risco: DoS/rate-limit de consultas se webhook for atacado. Correção futura: validar assinatura antes de consultar a API. |
| Alta | Exclusão em cascata da loja | Garantir confirmação forte, autorização e política de recuperação. |
| Média | Monkeypatch global de `reverse()` | Substituir por helpers/URLConf explícitos e testes de tenant. |
| Média | Cache local em serverless | Configurar Redis ou aceitar ausência de cache compartilhado. |
| Média | Fallback S3/AWS ainda existe | Remover após confirmar que produção usa apenas Supabase. |
| Média | README contém observações antigas de Storage | Atualizar documentação para refletir Storage Supabase já implementado. |
| Média | Encoding inconsistente em alguns arquivos | Normalizar UTF-8 sem alterar comportamento. |
| Baixa | Nomes legados `MODALINK_*` | Remover após conferir variáveis de produção. |

## Concluído recentemente

- CSS global monolítico (`static/css/catalogo.css`) foi modularizado, dividindo as regras em folhas de estilo específicas (`variables.css`, `landing.css`, `auth.css`, `dashboard.css` e o `catalogo.css` residual), e todos os templates da aplicação foram atualizados para carregar apenas os estilos necessários.
- `loja/views.py` refatorado e dividido em domain services (`auth`, `billing`, `catalog`, `products`, `store`, `lead`), reduzindo o tamanho de `views.py` para 883 linhas e mantendo apenas a orquestração HTTP.
- PostgreSQL/Auth/Storage consolidados no Supabase.
- Login Google configurado e publicado.
- Deploy principal em `vestlink.vercel.app`.
- Termos de Uso e Política de Privacidade publicados em rotas públicas.
- Cadastro e novos usuários via Google registram `AceiteLegal` versionado.
- Leads antigos podem ser anonimizados pela rotina cron via `LEAD_RETENTION_DAYS`.
- Sentry deixou de enviar PII por padrão (`SENTRY_SEND_DEFAULT_PII=0`).

## Relacionados

- [[visao-geral]] ajuda a priorizar dívidas pelo impacto no produto.
- [[arquitetura-do-sistema]] aponta acoplamentos e limites do monólito.
- [[endpoints-e-superficies]] ajuda a localizar superfícies afetadas por segurança e UX.
- [[fluxos-principais]] conecta LGPD, webhook, assinatura, vendedor e auth.
- [[modelo-de-dados]] mostra entidades envolvidas em exclusão, anonimização e pagamentos.
- [[integracoes]] liga dívidas a Supabase, Mercado Pago, e-mail, Redis e Sentry.
- [[gotchas-de-producao]] registra sintomas práticos dessas dívidas.

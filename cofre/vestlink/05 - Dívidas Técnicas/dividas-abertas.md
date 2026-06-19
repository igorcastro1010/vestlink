---
tipo: divida
status: ativo
prioridade: alta
revisado_em: 2026-06-16
fontes:
  - ../../../config/settings.py
  - ../../../loja/apps.py
  - ../../../loja/views.py
  - ../../../README.md
---

# Dívidas abertas

> [!summary] TL;DR
> Antes de escalar comercialmente, priorizar revisão jurídica, segurança fina,
> observabilidade e redução do acoplamento em views.

| Prioridade | Dívida | Risco / próximo passo |
|---|---|---|
| Alta | Revisão jurídica dos Termos e Privacidade | Textos base e aceite versionado existem; falta validação com profissional jurídico. |
| Alta | Direitos LGPD operacionais | Leads antigos são anonimizados; ainda faltam fluxo de exportação/exclusão por titular e canal formal. |
| Alta | Assinatura real do webhook Mercado Pago | Webhook aceita só POST e consulta o gateway; ainda falta validar assinatura oficial do Mercado Pago. |
| Alta | Exclusão em cascata da loja | Garantir confirmação forte, autorização e política de recuperação. |
| Média | `loja/views.py` concentra muitos casos de uso | Extrair serviços por auth, catálogo, leads e billing. |
| Média | Monkeypatch global de `reverse()` | Substituir por helpers/URLConf explícitos e testes de tenant. |
| Média | Cache local em serverless | Configurar Redis ou aceitar ausência de cache compartilhado. |
| Média | Fallback S3/AWS ainda existe | Remover após confirmar que produção usa apenas Supabase. |
| Média | README contém observações antigas de Storage | Atualizar documentação para refletir Storage Supabase já implementado. |
| Média | Encoding inconsistente em alguns arquivos | Normalizar UTF-8 sem alterar comportamento. |
| Baixa | CSS global muito extenso | Separar landing, auth, painel e catálogo gradualmente. |
| Baixa | Nomes legados `MODALINK_*` | Remover após conferir variáveis de produção. |

## Concluído recentemente

- PostgreSQL/Auth/Storage consolidados no Supabase.
- Login Google configurado e publicado.
- Deploy principal em `vestlink.vercel.app`.
- Termos de Uso e Política de Privacidade publicados em rotas públicas.
- Cadastro e novos usuários via Google registram `AceiteLegal` versionado.
- Leads antigos podem ser anonimizados pela rotina cron via `LEAD_RETENTION_DAYS`.
- Sentry deixou de enviar PII por padrão (`SENTRY_SEND_DEFAULT_PII=0`).

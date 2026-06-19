---
tipo: arquitetura
status: ativo
revisado_em: 2026-06-16
fontes:
  - ../../../config/urls.py
  - ../../../config/urls_tenant.py
---

# Endpoints e superfícies

> [!summary] TL;DR
> Existem quatro superfícies: marketing/autenticação, painel privado, catálogo
> público e integrações. A fonte exata das rotas é `config/urls.py`.

## Marketing e conta

- `/`: landing page.
- `/planos/`: oferta.
- `/termos/` e `/privacidade/`: documentos legais públicos.
- `/cadastro/`: criação de usuário e primeira loja.
- `/entrar/` e `/entrar/google/`: login.
- `/senha/...`: recuperação de senha.
- `/cadastro/supabase-confirmar/...`: callback e troca de sessão Supabase.

## Painel privado

- `/painel/`: lista e criação de lojas.
- `/painel/<slug>/`: dashboard da loja.
- Subrotas: editar/remover loja, QR Code, assinatura, checkout, categorias,
  produtos e exportação de leads.
- Autorização central: `_loja_do_usuario` em `loja/views.py`.

## Catálogo público

- `/c/<slug>/`: URL curta preferencial.
- `/loja/<slug>/`: URL legada/completa.
- Produto, WhatsApp individual e carrinho ficam sob essas superfícies.
- Domínio próprio ou subdomínio troca para `config.urls_tenant`, removendo o
  slug das URLs públicas.

## Integrações

- `/api/pagamentos/mercado-pago/webhook/`: webhook de pagamento; aceita apenas POST e consulta o gateway pelo ID.
- `/api/tasks/cron/`: verificação de trials e anonimização de leads antigos; exige `CRON_SECRET` fora de debug.
- `/gerenciador-vestlink/`: Django Admin.

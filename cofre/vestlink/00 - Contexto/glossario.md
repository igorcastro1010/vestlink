---
tipo: glossario
status: ativo
revisado_em: 2026-06-15
fontes:
  - ../../../loja/models.py
---

# Glossário

> [!summary] TL;DR
> Use estes termos para evitar confundir assinatura do SaaS, pedido do cliente
> final e vínculo do vendedor.

| Termo | Significado |
|---|---|
| Loja | Tenant e unidade comercial pertencente a um usuário. |
| Lojista / dono | Usuário Django associado a `Loja.usuario`. |
| Catálogo | Vitrine pública acessada por slug, subdomínio ou domínio próprio. |
| Link curto | Rota pública `/c/<slug>/`. |
| Vendedor | Pessoa vinculada a uma loja, opcionalmente com usuário próprio. |
| Código do vendedor | Slug único dentro da loja usado como referência. |
| Lead | Intenção de compra enviada ao WhatsApp, não uma venda fiscal concluída. |
| Sacolinha | Pedido com vários itens; origem de lead `sacolinha`. |
| Variação | Combinação de cor, tamanho, estoque e disponibilidade. |
| Premium | Único plano atualmente modelado. |
| Trial | Período padrão de sete dias da loja. |
| Assinatura | Estado comercial da loja: trial, ativa, vencida ou cancelada. |
| Pagamento | Registro de cobrança do SaaS pelo Mercado Pago. |
| Tenant | Loja resolvida pelo host no `TenantMiddleware`. |

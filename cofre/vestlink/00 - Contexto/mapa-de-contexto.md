---
tipo: contexto
status: ativo
revisado_em: 2026-06-19
fontes:
  - ../../../README.md
  - ../../../config/settings.py
  - ../../../config/urls.py
---

# Mapa de contexto

> [!summary] TL;DR
> VestLink é um SaaS Django monolítico para lojistas criarem catálogos de moda,
> captarem pedidos pelo WhatsApp e acompanharem leads, vendedores e assinatura.
> Produção roda na Vercel; PostgreSQL, Auth e arquivos usam Supabase.

## Comece pela necessidade

| Necessidade | Nota |
|---|---|
| Entender produto e estado atual | [[visao-geral]] |
| Nomes usados no projeto | [[glossario]] |
| Componentes e responsabilidades | [[../01 - Arquitetura/arquitetura-do-sistema]] |
| Rotas e superfícies | [[../01 - Arquitetura/endpoints-e-superficies]] |
| Cadastro, Google, catálogo, WhatsApp e pagamento | [[../01 - Arquitetura/fluxos-principais]] |
| Serviços externos e variáveis | [[../01 - Arquitetura/integracoes]] |
| Entidades e relacionamentos | [[../02 - Banco de Dados/modelo-de-dados]] |
| Motivos das escolhas atuais | [[../03 - Decisões/indice-de-decisoes]] |
| Armadilhas já conhecidas | [[../04 - Aprendizados/gotchas-de-producao]] |
| Riscos e trabalho pendente | [[../05 - Dívidas Técnicas/dividas-abertas]] |

## Ponteiros rápidos para código

- Configuração: `config/settings.py`
- Rotas: `config/urls.py`, `config/urls_tenant.py`
- Domínio: `loja/models.py`
- Orquestração HTTP: `loja/views.py`
- Serviços de Domínio: `loja/services/`
- Formulários: `loja/forms.py`
- Auth Supabase: `loja/supabase_auth.py`
- Storage Supabase: `loja/storage.py`
- Pagamentos: `loja/payments.py`
- UI: `loja/templates/`, `static/css/catalogo.css`, `static/js/`
- Deploy: `vercel.json`, `api/index.py`
- Testes: `loja/tests.py`

## Regra de atualização

Se uma tarefa mudar um dos ponteiros acima de forma estrutural, revise a nota
correspondente e atualize `revisado_em`.

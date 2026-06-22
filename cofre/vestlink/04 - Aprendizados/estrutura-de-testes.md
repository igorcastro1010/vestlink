---
tipo: aprendizado
status: ativo
revisado_em: 2026-06-21
fontes:
  - ../../../loja/tests/
---

# Estrutura de Testes Modularizados

> [!important]
> O antigo arquivo monolítico `loja/tests.py` foi **completamente removido** para evitar lentidão e consumo excessivo de tokens. 
> 
> **ATENÇÃO AGENTES:** NUNCA recriem o arquivo `loja/tests.py`. Toda nova suíte de testes ou modificação deve ser feita dentro do pacote `loja/tests/`, respeitando a modularização por domínio.

---

## 1. Organização do Diretório `loja/tests/`

Os testes foram separados de forma estrita por contexto de domínio do negócio e infraestrutura:

| Arquivo | Domínio / Responsabilidade |
| :--- | :--- |
| `test_infra.py` | Testes de integração de infra (ex.: integração direta com storage do Supabase). |
| `test_auth.py` | Fluxo de autenticação, login, cadastro de lojista, confirmações de e-mail e OAuth do Google. |
| `test_catalogo.py` | Página pública do catálogo, vitrine, busca, paginação, filtros, fragmentos AJAX e middleware de Tenant. |
| `test_products.py` | Cadastro, edição e exclusão de produtos, controle de estoque, galeria de fotos e WebP/signals. |
| `test_leads.py` | Integração do WhatsApp, cliques, sacolinha/carrinho, atribuição de vendedores e exportação de leads (CSV/Impressão). |
| `test_dashboard.py` | Painel administrativo do lojista, gráficos, controle de acessos de vendedores e remoção de lojas. |
| `test_billing.py` | Gestão de assinaturas (ativa/vencida/trial), checkout Mercado Pago, webhook, validação de cupons e cron/management commands de cobrança. |

---

## 2. Comandos Recomendados para Desenvolvimento (Foco por Domínio)

Para desenvolvimento ágil e economia de recursos, execute apenas a suíte do domínio no qual está trabalhando:

* **Infraestrutura**:
  ```bash
  python manage.py test loja.tests.test_infra
  ```
* **Autenticação**:
  ```bash
  python manage.py test loja.tests.test_auth
  ```
* **Catálogo (Vitrine Pública)**:
  ```bash
  python manage.py test loja.tests.test_catalogo
  ```
* **Produtos**:
  ```bash
  python manage.py test loja.tests.test_products
  ```
* **Leads / WhatsApp / Sacolinha**:
  ```bash
  python manage.py test loja.tests.test_leads
  ```
* **Dashboard / Painel Lojista**:
  ```bash
  python manage.py test loja.tests.test_dashboard
  ```
* **Faturamento / Cobrança / Webhook / Cron**:
  ```bash
  python manage.py test loja.tests.test_billing
  ```

---

## 3. Quando Rodar a Suíte Completa

A suíte de testes completa deve ser executada nas seguintes situações:
1. **Antes de abrir Pull Requests ou enviar Pushes para o branch `main`**.
2. **Ao realizar alterações que afetem signals globais, middlewares transversais ou modelos compartilhados** (ex.: alterações em `models.py` da loja).
3. **Nas verificações finais de CI locais.**

Comando para rodar a suíte completa:
```bash
python manage.py test loja
```

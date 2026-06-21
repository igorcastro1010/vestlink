---
tipo: contexto
status: ativo
revisado_em: 2026-06-21
fontes:
  - ./mapa-de-contexto.md
  - ../../../loja/views.py
  - ../../../loja/models.py
  - ../../../loja/tests.py
---

# Índice Rápido para Desenvolvimento Econômico

> [!summary] TL;DR
> Este guia orienta Codex/Antigravity na seleção estrita de quais arquivos ler e quais ignorar
> para tarefas comuns no VestLink. Use-o para economizar tokens e evitar varreduras desnecessárias.

---

## 1. Autenticação e Cadastro (Auth)

* **Tarefa Comum:** Modificar fluxo de login, cadastro de lojista, login social com Google, confirmação de e-mail (via Supabase ou Django) ou recuperação de senha.
* **Arquivos que DEVEM ser lidos:**
  - [supabase_auth.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/supabase_auth.py) — Integração de autenticação/OAuth do Supabase.
  - [auth.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/services/auth.py) — Lógica de domínio do cadastro e e-mail.
  - [forms.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/forms.py) (apenas a classe `CadastroForm`).
  - [views.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/views.py) (apenas views `LoginLojistaView`, `cadastro`, `google_oauth_start`, `supabase_confirmar_email`, `reenviar_confirmacao_email`).
  - [cadastro.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/cadastro.html) e [login.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/login.html).
* **Arquivos que NÃO devem ser lidos:**
  - `loja/services/store.py`, `loja/services/billing.py`, `loja/services/catalog.py` (lógicas comerciais).
  - Outros templates do painel administrativo ou catálogo público.
* **Skill Recomendada:** `security-review` (em alterações de fluxo de acesso) ou `forms-ux-polish` (em alterações de interface/formulários).
* **Teste Mínimo Recomendado:**
  - `python manage.py test loja.tests.CatalogoTests.test_cadastro_cria_conta_pendente_e_confirma_por_email`
  - `python manage.py test loja.tests.CatalogoTests.test_google_oauth_cria_usuario_local_e_autentica`

---

## 2. Catálogo (Vitrine Pública)

* **Tarefa Comum:** Ajustar a listagem de produtos, busca, paginação com AJAX, filtros de categorias ou exibição do produto na vitrine pública.
* **Arquivos que DEVEM ser lidos:**
  - [catalog.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/services/catalog.py) — Lógica de consulta dos produtos do catálogo.
  - [views.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/views.py) (apenas views `catalogo`, `catalogo_curto`, `produto_detalhe`).
  - [catalogo.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/catalogo.html), [produto_detalhe.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/produto_detalhe.html) e [produto_grid.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/includes/produto_grid.html).
  - [middleware.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/middleware.py) — Caso envolva resolução de subdomínio/domínio personalizado.
* **Arquivos que NÃO devem ser lidos:**
  - `loja/services/auth.py`, `loja/services/billing.py` (faturamento/cadastro).
  - Templates de painel administrativo (`painel_loja.html`, `editar_loja.html`).
* **Skill Recomendada:** `catalog-design-conversion` (para conversão/UX), `mobile-ux-design` (para responsividade do catálogo).
* **Teste Mínimo Recomendado:**
  - `python manage.py test loja.tests.CatalogoTests.test_catalogo_publico_renderiza_produto`
  - `python manage.py test loja.tests.CatalogoTests.test_paginacao_catalogo_primeira_pagina`

---

## 3. Produto (Cadastro e Variações)

* **Tarefa Comum:** Modificar campos de cadastro de peça, galeria de fotos extras, tamanhos/cores, estoque por variação e otimização de imagens.
* **Arquivos que DEVEM ser lidos:**
  - [models.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/models.py) (classes `Produto`, `ProdutoImagem`, `ProdutoVariacao`).
  - [products.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/services/products.py) — Orquestração de criação/edição/remoção de peças.
  - [forms.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/forms.py) (apenas a classe `ProdutoForm`).
  - [utils.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/utils.py) — Funções de otimização/conversão WebP.
  - [editar_produto.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/editar_produto.html) e [remover_produto.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/remover_produto.html).
* **Arquivos que NÃO devem ser lidos:**
  - `loja/supabase_auth.py` ou `loja/payments.py`.
  - Templates de login/cadastro ou termos de privacidade.
* **Skill Recomendada:** `forms-ux-polish` (UX de formulário de cadastro de produtos).
* **Teste Mínimo Recomendado:**
  - `python manage.py test loja.tests.CatalogoTests.test_painel_cadastra_produto`
  - `python manage.py test loja.tests.SaasOptimizationsTests.test_image_optimized_and_converted_to_webp`

---

## 4. Dashboard (Painel Lojista)

* **Tarefa Comum:** Ajustar onboarding do lojista, gráficos de resumo comercial (leads por dia, produtos mais clicados), gestão de vendedores e categorias no painel.
* **Arquivos que DEVEM ser lidos:**
  - [store.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/services/store.py) — Orquestração de dados do dashboard administrativo e QR Code.
  - [views.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/views.py) (views `painel_loja`, `painel`, `baixar_qr_code`).
  - [painel_loja.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/painel_loja.html) e [painel.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/painel.html).
* **Arquivos que NÃO devem ser lidos:**
  - `loja/services/auth.py`, `loja/services/billing.py`.
  - Templates do catálogo público (`catalogo.html`, `produto_detalhe.html`).
* **Skill Recomendada:** `dashboard-design` (design do painel), `table-list-ux` (visualização de dados).
* **Teste Mínimo Recomendado:**
  - `python manage.py test loja.tests.CatalogoTests.test_painel_renderiza_area_da_loja`
  - `python manage.py test loja.tests.SaasOptimizationsTests.test_dashboard_charts_context_variables`

---

## 5. Leads / WhatsApp

* **Tarefa Comum:** Customizar mensagem do carrinho/sacolinha enviada ao WhatsApp, regras de atribuição de vendedor (leads diretos ou referenciados) e exportações de leads.
* **Arquivos que DEVEM ser lidos:**
  - [models.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/models.py) (classes `Lead`, `Vendedor`).
  - [lead.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/services/lead.py) — Lógica de criação de leads e montagem de URLs WhatsApp.
  - [views.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/views.py) (views `whatsapp_produto`, `whatsapp_carrinho`, `exportar_leads_csv`, `exportar_leads_impressao`).
  - [validators.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/validators.py) e [validators.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/validators.py) (limpeza/validação de telefone).
  - [leads_impressao.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/leads_impressao.html).
* **Arquivos que NÃO devem ser lidos:**
  - `loja/supabase_auth.py`, `loja/storage.py` (infraestrutura/auth).
  - Templates da área de faturamento ou planos.
* **Skill Recomendada:** `copywriting-ux` (mensagens e fluxos de conversa), `table-list-ux` (relatório e listagens de leads).
* **Teste Mínimo Recomendado:**
  - `python manage.py test loja.tests.CatalogoTests.test_whatsapp_produto_contabiliza_clique`
  - `python manage.py test loja.tests.NovosRecursosSaaSTests.test_whatsapp_carrinho_salva_tipo_entrega_e_endereco`

---

## 6. Faturamento e Assinaturas (Billing)

* **Tarefa Comum:** Ajustar planos, cupons de desconto, checkout com Mercado Pago (API de preferências), processamento de retornos e Webhooks.
* **Arquivos que DEVEM ser lidos:**
  - [models.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/models.py) (classes `Pagamento`, `Cupom`, campos de assinatura em `Loja`).
  - [billing.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/services/billing.py) — Controle de dados do checkout e webhook.
  - [payments.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/payments.py) — SDK/Requisições diretas à API do Mercado Pago.
  - [views.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/views.py) (views `assinatura`, `checkout_premium`, `pagamento_retorno`, `mercado_pago_webhook`).
  - [checkout_premium.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/checkout_premium.html), [assinatura.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/assinatura.html) e [pagamento_retorno.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/pagamento_retorno.html).
* **Arquivos que NÃO devem ser lidos:**
  - `loja/supabase_auth.py`, `loja/storage.py`.
  - Templates de catálogo, produtos ou categorias.
* **Skill Recomendada:** `security-review` (para webhooks e segurança de preços/cupons).
* **Teste Mínimo Recomendado:**
  - `python manage.py test loja.tests.CatalogoTests.test_checkout_mercado_pago_cria_preferencia_e_redireciona`
  - `python manage.py test loja.tests.CatalogoTests.test_webhook_mercado_pago_atualiza_pagamento`

---

## 7. CSS e Responsividade Mobile

* **Tarefa Comum:** Modificar grids de vitrine, alinhamento de touch targets, ajustes de menus de navegação móvel e temas estéticos da loja.
* **Arquivos que DEVEM ser lidos:**
  - [catalogo.css](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/static/css/catalogo.css) — Folha de estilo do storefront.
  - Visualizar o template específico sob edição (ex: [catalogo.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/catalogo.html), [painel_loja.html](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/loja/templates/painel_loja.html)).
* **Arquivos que NÃO devem ser lidos:**
  - Praticamente nenhum arquivo da pasta `loja/services/`.
  - `loja/supabase_auth.py`, `loja/payments.py`.
* **Skill Recomendada:** `mobile-ux-design` (ajuste responsivo), `saas-ui-polish` (melhoria estética), `brand-design-system` (consistência de cores/tokens), `motion-microinteractions` (animações e hovers).
* **Teste Mínimo Recomendado:**
  - Verificação visual via browser (Playwright ou screenshot) + `python manage.py test loja.tests.CatalogoTests.test_catalogo_publico_renderiza_produto` (valida o esqueleto HTML).

---

## 8. Configuração de Deploy

* **Tarefa Comum:** Modificar rotas da Vercel, regras de rewrite globais, WSGI serverless entrypoint ou configurações gerais do Django vinculadas ao ambiente.
* **Arquivos que DEVEM ser lidos:**
  - [vercel.json](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/vercel.json) — Configurações de rotas, builds e rewrites da Vercel.
  - [index.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/api/index.py) — Entrypoint WSGI para a Vercel.
  - [settings.py](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/config/settings.py) — Configurações do Django (variáveis de ambiente, hosts permitidos, security cookies).
* **Arquivos que NÃO devem ser lidos:**
  - Toda a lógica de negócios em `loja/services/` e arquivos de templates HTML/CSS.
* **Skill Recomendada:** `performance-audit` (se envolver otimização de headers de cache na Vercel).
* **Teste Mínimo Recomendado:**
  - `python manage.py test` para garantir integridade + checagem sintática do arquivo `vercel.json`.

---

## 9. Manutenção de Documentação e Cofre

* **Tarefa Comum:** Atualizar notas Obsidian do cofre, registrar decisões arquiteturais, adicionar aprendizados/gotchas e atualizar pendências técnicas.
* **Arquivos que DEVEM ser lidos:**
  - [mapa-de-contexto.md](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/cofre/vestlink/00%20-%20Contexto/mapa-de-contexto.md) — Visão de ponteiros do cofre.
  - [AGENTS.md](file:///c:/Users/igorc/OneDrive/Área de Trabalho/Projeto/cofre/vestlink/AGENTS.md) — Protocolo de uso do cofre.
  - A nota Obsidian específica que será editada (dentro de `cofre/vestlink/`).
* **Arquivos que NÃO devem ser lidos:**
  - Qualquer código da aplicação (a menos que seja explicitamente listado na seção `fontes` da nota para validação de discrepância).
* **Skill Recomendada:** `docs-cofre-sync` (para atualização e auditoria de notas).
* **Teste Mínimo Recomendado:**
  - Inspeção visual de renderização do Markdown e validação de links internos do cofre.

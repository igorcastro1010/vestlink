---
tipo: metadocumento
status: ativo
revisado_em: 2026-06-21
fontes:
  - ../04 - Aprendizados/estrutura-de-testes.md
---

# Diretrizes de Comandos Seguros e Econômicos

Este metadocumento estabelece os padrões e comandos mínimos recomendados que todos os agentes (como Codex/Antigravity) devem seguir ao trabalhar no projeto **VestLink**. O objetivo é maximizar a eficiência, economizar tokens e evitar execuções pesadas desnecessárias da suíte de testes.

> [!danger] Regra de Ouro: Não recriar loja/tests.py
> O arquivo monolítico `loja/tests.py` foi **deletado**. **NUNCA** o recrie. Toda a estrutura de testes foi modularizada sob o diretório `loja/tests/`.

---

## 1. Tabela de Comandos Mínimos por Domínio

Antes de fazer testes gerais, utilize o comando correspondente ao contexto exato da sua tarefa:

| Tipo de Tarefa / Alteração | Comando Mínimo Recomendado |
| :--- | :--- |
| **Checagem Geral (Estática)** | `python manage.py check` |
| **Autenticação (Auth)** | `python manage.py test loja.tests.test_auth` |
| **Catálogo (Vitrine Pública)** | `python manage.py test loja.tests.test_catalogo` |
| **Produtos e Estoque** | `python manage.py test loja.tests.test_products` |
| **Leads / WhatsApp / Sacolinha** | `python manage.py test loja.tests.test_leads` |
| **Dashboard / Painel Lojista** | `python manage.py test loja.tests.test_dashboard` |
| **Faturamento / Cobrança (Billing)** | `python manage.py test loja.tests.test_billing` |
| **Infraestrutura / Storage (Supabase)** | `python manage.py test loja.tests.test_infra` |
| **Suíte Completa** | `python manage.py test loja` |

---

## 2. Diretrizes de Execução

### Quando usar Teste Específico
* **Durante a codificação e correção de bugs**: Utilize sempre o teste específico do arquivo do domínio ou do método que está sendo alterado (ex: `python manage.py test loja.tests.test_products.ProductTests.test_painel_cadastra_produto`).
* **Não rode testes desnecessários**: Se você está ajustando uma validação no formulário de produtos, não há motivo para rodar testes de cobrança do Mercado Pago.

### Quando usar Suíte Completa
Rode a suíte de testes completa (`python manage.py test loja`) **apenas** nas seguintes situações:
1. **Verificação final local**: Imediatamente antes de realizar um `git push` ou abrir um Pull Request para `main`.
2. **Mudanças transversais**: Se alterar middlewares de tenant, configurações gerais de `settings.py`, signals globais ou se realizar migrações de banco de dados (`makemigrations`).

---

## 3. Instruções para Agentes
* **Economia de Recursos**: Sempre limite os escopos de comandos de teste para reduzir processamento desnecessário na máquina de desenvolvimento e economizar tempo na resposta.
* **Validação de Sintaxe**: Prefira rodar primeiro `python manage.py check` para certificar-se de que não há falhas sintáticas ou de inicialização do Django antes de subir o banco de dados de teste.

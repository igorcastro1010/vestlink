---
tipo: arquitetura
status: ativo
revisado_em: 2026-06-29
fontes:
  - ../../../loja/views.py
  - ../../../loja/services/
  - ../../../loja/forms.py
  - ../../../loja/supabase_auth.py
  - ../../../loja/payments.py
---

# Fluxos principais

> [!summary] TL;DR
> O Django mantém o usuário operacional localmente. Supabase confirma identidade
> e e-mail; Abacate Pay confirma a assinatura; WhatsApp recebe a conversão.

## Cadastro por e-mail

1. `CadastroForm` exige aceite dos Termos de Uso e Política de Privacidade.
2. A view registra `AceiteLegal` com versões, fonte, IP e navegador.
3. `CadastroForm` cria usuário inativo e primeira loja.
4. Supabase Auth recebe o signup quando habilitado.
5. Link retorna a `/cadastro/supabase-confirmar/`.
6. Frontend entrega token à view de sessão.
7. Django valida no Supabase, ativa e autentica o usuário local.

## Google OAuth

1. `/entrar/google/` verifica se o provider está ativo.
2. Navegador vai ao Supabase e depois ao Google.
3. Callback retorna ao template de confirmação.
4. Token Supabase é validado no servidor.
5. Usuário Django é localizado ou criado com senha inutilizável.
6. Usuário criado por Google registra `AceiteLegal` com fonte `google_oauth`.
7. Sessão local é aberta e usuário segue ao painel.

## Catálogo e WhatsApp

1. Loja é resolvida por slug ou tenant.
2. Catálogo bloqueia assinatura inativa.
3. Cliente escolhe produto, cor, tamanho e opcionalmente vários itens.
4. View registra `Lead`, vendedor de referência e metadados.
5. Resposta redireciona para URL do WhatsApp da loja com mensagem pronta.
6. Leads antigos são anonimizados pela rotina cron conforme `LEAD_RETENTION_DAYS`.

## Vendedor

1. Dono cria `Vendedor` com código único por loja.
2. Link do catálogo carrega a referência do vendedor.
3. Leads guardam `vendedor_id`.
4. Usuário associado ao vendedor acessa apenas a loja permitida e seus dados
   são filtrados no painel.

## Assinatura

1. Loja começa em trial de sete dias.
2. Pagamento cria `Pagamento` local e checkout hospedado na Abacate Pay.
3. Lojista paga na URL retornada pela Abacate Pay.
4. Webhook `checkout.completed` confirma o pagamento, com validação de secret/assinatura quando configurada.
5. Aprovação ativa a assinatura da loja.
6. Cron marca trials expirados como vencidos e anonimiza leads antigos.

## Relacionados

- [[glossario]] padroniza nomes como Lead, Sacolinha, Vendedor, Trial e Pagamento.
- [[endpoints-e-superficies]] mostra as rotas que executam estes fluxos.
- [[modelo-de-dados]] descreve `Loja`, `Vendedor`, `Lead`, `AceiteLegal` e `Pagamento`.
- [[integracoes]] detalha Supabase Auth, Google OAuth, Abacate Pay, Resend/SMTP e WhatsApp.
- [[ADR-003 - Identidade hibrida Django e Supabase]] explica a identidade local + externa.
- [[gotchas-de-producao]] lista armadilhas de callback, e-mail, webhook e cron.
- [[dividas-abertas]] acompanha pendências de LGPD, webhook e acoplamento.

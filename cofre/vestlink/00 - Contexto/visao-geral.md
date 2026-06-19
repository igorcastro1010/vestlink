---
tipo: contexto
status: ativo
revisado_em: 2026-06-15
fontes:
  - ../../../README.md
  - ../../../loja/models.py
  - ../../../config/urls.py
---

# Visão geral

> [!summary] TL;DR
> O VestLink entrega catálogo público, pedido pelo WhatsApp e painel operacional
> para pequenas lojas de moda. O modelo atual é Premium por loja, com teste de
> 7 dias e preço-base registrado de R$ 39,90.

## Usuários

- **Dono da loja:** cria e configura lojas, produtos, categorias, vendedores,
  assinatura e relatórios.
- **Vendedor:** acessa a loja vinculada e acompanha leads atribuídos ao seu link.
- **Cliente final:** navega no catálogo, escolhe variações, informa dados e abre
  uma mensagem pronta no WhatsApp.
- **Administrador VestLink:** usa o Django Admin em `/gerenciador-vestlink/`.

## Capacidades atuais

- Cadastro por usuário/senha com confirmação de e-mail.
- Login e criação de conta com Google via Supabase OAuth.
- Uma conta pode possuir várias lojas.
- Logo, banner, cor, tema, Instagram, domínio e link curto por loja.
- Categorias, produtos, galeria, variações e estoque.
- Carrinho/sacolinha e contato direto pelo WhatsApp.
- Leads com cliente, vendedor, produto, entrega, endereço e status.
- Links de referência por vendedor.
- QR Code do catálogo.
- Trial, assinatura Premium, cupom e Mercado Pago.
- Exportação de leads em CSV e formato para impressão.
- Tema claro/escuro e layout responsivo em evolução.

## Produção

- URL principal: `https://vestlink.vercel.app`
- Runtime: Django WSGI em função Python da Vercel.
- Dados persistentes: PostgreSQL do Supabase.
- Arquivos: Supabase Storage quando habilitado.
- Auth externo: Supabase Auth, incluindo Google.

## Fora do escopo confirmado

- Emissão fiscal automática.
- Termos de Uso e Política de Privacidade implementados no produto.
- Aplicativo móvel nativo.
- Checkout completo de produtos; a conversão final ocorre no WhatsApp.

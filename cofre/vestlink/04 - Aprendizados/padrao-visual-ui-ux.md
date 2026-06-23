---
tipo: aprendizado
status: ativo
revisado_em: 2026-06-23
fontes:
  - ../../../static/css/catalogo.css
  - ../../../static/css/variables.css
  - ../../../static/js/theme.js
  - ../../../loja/templates/login.html
  - ../../../loja/templates/cadastro.html
  - ../../../loja/templates/painel.html
  - ../../../loja/templates/painel_loja.html
  - ../../../loja/templates/catalogo.html
  - ../../../loja/templates/produto_detalhe.html
  - ../../../loja/templates/assinatura.html
---

# Padrao Visual UI/UX do VestLink

TL;DR: O VestLink usa Django com templates HTML, CSS global em `static/css/catalogo.css`, variáveis em `static/css/variables.css` e JavaScript progressivo. Não há React/Next/Tailwind no stack atual. O projeto é exclusivamente **Dark Mode único**, tendo o tema escuro como padrão único em todo o ecossistema.

## Decisão Visual: Dark Mode Único

- **Modo Claro Removido**: O modo claro foi completamente desativado como tema ativo.
- **Estrutura Padrão**: O atributo `data-theme="dark"` é injetado diretamente na tag `<html>` de todos os templates principais para carregamento instantâneo.
- **Javascript do Tema**: O arquivo `theme.js` está configurado para sempre retornar e forçar o tema `"dark"`, gravando este valor no `localStorage` e desativando controles de alternância.
- **Sem Botões de Alternância**: Os botões e toggles `.dark-mode-toggle` foram ocultados via CSS (`display: none !important;`) e Javascript. **Não recriar ou reintroduzir botões de tema claro/escuro** sem uma decisão explícita de arquitetura.
- **Novas Telas**: Qualquer nova página ou componente a ser criado **deve nascer diretamente e exclusivamente em dark mode**, seguindo os tokens e cores globais.

## Direcao Visual

- Visual SaaS premium, limpo e profissional, mantendo roxo/lilás desaturado e tons escuros como identidade.
- Componentes principais utilizam a escala `--uix-*` e variáveis globais do `:root` configuradas no modo escuro em `variables.css`.
- Cards, botões, inputs, tabelas e containers devem priorizar contraste alto, espaçamento generoso, bordas arredondadas moderadas e estados de foco visíveis.
- Manter legibilidade perfeita de textos normal, títulos, placeholders, inputs, alertas e status nos fundos escuros.
- Microinterações devem ser discretas: `transform`, `opacity`, `box-shadow` e transições curtas, respeitando `prefers-reduced-motion`.

## Regras praticas

- Não adicionar dependências grandes de UI enquanto o projeto seguir server-rendered Django.
- Ao alterar CSS visual, atualizar o cache bust do `catalogo.css?v=...` nos templates afetados.
- Preferir ajustar as variáveis do `:root` no fim de `catalogo.css` ou em `variables.css` em vez de espalhar cores fixas por componentes.
- Em telas escuras, nunca usar cores herdadas escuras como `#111` em cards escuros; reforcar titulos com `--uix-text-strong` (ou `--ink`) e textos secundarios com `--uix-text-muted` (ou `--muted`).
- Verificar visualmente pelo menos landing, login/cadastro, painel de lojas, dashboard da loja, catálogo público e assinatura após grandes mudanças visuais.

## Relacionados

- [[visao-geral]] mostra as telas e jornadas que precisam manter consistência visual.
- [[arquitetura-do-sistema]] confirma o stack Django/templates/CSS global.
- [[endpoints-e-superficies]] ajuda a escolher as superfícies para teste visual.
- [[skill-ui-ux-pro-max]] descreve a skill local usada como guia de UI/UX.
- [[dividas-abertas]] acompanha a dívida de CSS global extenso.

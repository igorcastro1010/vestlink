---
tipo: aprendizado
status: ativo
revisado_em: 2026-06-18
fontes:
  - ../../../static/css/catalogo.css
  - ../../../loja/templates/login.html
  - ../../../loja/templates/cadastro.html
  - ../../../loja/templates/painel.html
  - ../../../loja/templates/painel_loja.html
  - ../../../loja/templates/catalogo.html
  - ../../../loja/templates/produto_detalhe.html
  - ../../../loja/templates/assinatura.html
---

# Padrao Visual UI/UX do VestLink

TL;DR: O VestLink usa Django com templates HTML, CSS global em `static/css/catalogo.css` e JavaScript progressivo. Nao ha React/Next/Tailwind no stack atual, entao Framer Motion e componentes 21st.dev devem ser usados apenas como referencia visual; microinteracoes devem ser feitas com CSS/JS leve. A direcao visual atual e "soft premium": roxos menos saturados, sombras mais leves e contraste forte em light/dark.

## Direcao

- Visual SaaS premium, limpo e profissional, mantendo roxo/lilas como identidade, mas com saturacao controlada.
- Componentes principais devem usar tokens `--uix-*` para funcionar no tema claro e escuro.
- Cards, botoes, inputs, tabelas e containers devem priorizar contraste, espacamento generoso, bordas arredondadas moderadas, sombras suaves e estados de foco visiveis.
- Microinteracoes devem ser discretas: `transform`, `opacity`, `box-shadow` e transicoes curtas, respeitando `prefers-reduced-motion`.

## Regras praticas

- Nao adicionar dependencias grandes de UI enquanto o projeto seguir server-rendered Django.
- Ao alterar CSS visual, atualizar o cache bust do `catalogo.css?v=...` nos templates afetados.
- Preferir ajustar a escala `--uix-*` no fim de `catalogo.css` em vez de espalhar cores fixas por componentes.
- Roxos primarios devem ser mais calmos/desaturados; evitar gradientes muito luminosos ou blocos roxos em navegacao comum.
- Em telas escuras, nunca usar cores herdadas escuras como `#111` em cards escuros; reforcar titulos com `--uix-text-strong` e textos secundarios com `--uix-text-muted`.
- Chips, badges, abas e CTAs precisam ter pares de cor para claro e escuro.
- Verificar visualmente pelo menos landing, login/cadastro, painel de lojas, dashboard da loja, catalogo publico e assinatura apos grandes mudancas visuais.

## Relacionados

- [[visao-geral]] mostra as telas e jornadas que precisam manter consistência visual.
- [[arquitetura-do-sistema]] confirma o stack Django/templates/CSS global.
- [[endpoints-e-superficies]] ajuda a escolher as superfícies para teste visual.
- [[skill-ui-ux-pro-max]] descreve a skill local usada como guia de UI/UX.
- [[dividas-abertas]] acompanha a dívida de CSS global extenso.

# Protocolo de contexto do VestLink

Antes de explorar o código, consulte o cofre Obsidian em
`cofre/vestlink/00 - Contexto/mapa-de-contexto.md`.

Ordem de trabalho:

1. Leia o TL;DR do mapa e abra apenas as notas ligadas à tarefa.
2. Confie em notas com `status: ativo` e `revisado_em` recente.
3. Consulte o código indicado em `fontes` somente quando a nota não responder,
   houver risco de desatualização ou a tarefa exigir edição.
4. Não faça varreduras amplas se um arquivo ou módulo específico bastar.
5. Após descobrir algo estrutural e durável no código, atualize a nota
   correspondente do cofre na mesma tarefa.
6. Nunca registre segredos, tokens, senhas, dados pessoais ou conteúdo de `.env`.

Convenções completas: `cofre/vestlink/AGENTS.md`.

## Uso economico de skills

Antes de cada tarefa, consulte `cofre/vestlink` e carregue apenas as skills
relevantes em `.agents/skills`. Nao carregue todas as skills por padrao.
Priorize economia de tokens: escolha o menor conjunto que cubra a tarefa.

Mapeamento recomendado:

- UI geral: `saas-ui-polish`, `brand-design-system`, `theme-contrast-audit`
- Catalogo: `catalog-design-conversion`, `mobile-ux-design`, `copywriting-ux`
- Landing: `landing-page-design`, `copywriting-ux`
- Dashboard: `dashboard-design`, `table-list-ux`
- Forms: `forms-ux-polish`
- Mobile: `mobile-ux-design`
- Animacoes: `motion-microinteractions`
- Testes visuais: `visual-regression-playwright`
- Performance: `performance-audit`
- Seguranca: `security-review`
- Docs: `docs-cofre-sync`

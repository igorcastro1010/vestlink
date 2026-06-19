---
tipo: meta
status: ativo
revisado_em: 2026-06-15
fontes:
  - ../AGENTS.md
  - ../../../AGENTS.md
---

# Como usar com Codex

> [!summary] TL;DR
> O `AGENTS.md` da raiz manda o Codex começar pelo mapa. O código só é lido
> quando a nota não basta ou quando uma mudança precisa ser implementada.

## Início de tarefa

1. Identificar o domínio da pergunta.
2. Abrir [[../00 - Contexto/mapa-de-contexto]].
3. Ler no máximo as notas diretamente relacionadas.
4. Usar `fontes` para chegar ao menor conjunto possível de arquivos.

## Fim de tarefa

Atualizar o cofre somente quando houver conhecimento durável:

- nova entidade ou relação;
- novo fluxo ou integração;
- decisão arquitetural;
- gotcha confirmado;
- dívida criada ou resolvida.

Mudanças puramente visuais e correções triviais não precisam gerar notas, salvo
quando revelarem uma convenção reutilizável.

## Controle de desatualização

- `ativo`: pode orientar a tarefa.
- `revisar`: use como pista e confirme no código.
- `arquivado`: histórico, não referência atual.
- Ao confirmar divergência, corrija a nota na mesma tarefa.

---
tipo: aprendizado
status: ativo
revisado_em: 2026-06-18
fontes:
  - ../../../.agents/skills/ui-ux-pro-max/SKILL.md
  - ../../../src/ui-ux-pro-max
---

# Skill UI/UX Pro Max

> [!summary] TL;DR
> A skill `ui-ux-pro-max` foi instalada como recurso local do projeto em
> `.agents/skills/ui-ux-pro-max`, sem criar `CLAUDE.md`. Seus dados e scripts de
> apoio ficam em `src/ui-ux-pro-max`.

## Contexto

O VestLink usa uma convenção local `.agents` para skills de agente dentro do
projeto. A skill foi adaptada do repositório
`nextlevelbuilder/ui-ux-pro-max-skill`, mantendo a estrutura útil para consulta
por agentes sem acoplar o projeto a arquivos específicos do Claude.

## Invariantes

- Não criar `CLAUDE.md` para esta skill.
- Não mover a skill para `.claude`.
- Manter `.agents/skills/ui-ux-pro-max/data` e `scripts` apontando para
  `../../../src/ui-ux-pro-max/...`.
- Usar a skill como guia de UI/UX; ela não altera regras de negócio, banco,
  autenticação ou rotas.

## Pontos de mudança

- Skill principal: `.agents/skills/ui-ux-pro-max/SKILL.md`.
- Manifesto da skill: `.agents/skills/ui-ux-pro-max/skill.json`.
- Base de apoio: `src/ui-ux-pro-max/`.

## Relacionados

- [[padrao-visual-ui-ux]]
- [[arquitetura-do-sistema]]
- [[endpoints-e-superficies]]
- [[dividas-abertas]]

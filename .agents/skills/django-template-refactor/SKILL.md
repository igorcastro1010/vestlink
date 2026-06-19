---
name: django-template-refactor
description: Use to refactor VestLink Django templates safely, reducing duplication and improving markup/CSS structure without changing routes, context variables, auth, database, or business rules.
---

# Django Template Refactor

## Objetivo
Melhorar templates Django mantendo comportamento igual.

## Quando Usar
Use ao organizar HTML, includes, blocos, classes e estrutura visual.

## Checklist
- Consultar cofre e localizar template exato.
- Preservar nomes de campos, urls, csrf, forms e context.
- Manter acessibilidade basica e estados.
- Rodar `python manage.py check` quando possivel.

## Regras
- Nao alterar regra de negocio ou queries.
- Nao remover ids/classes usados por JS sem verificar.
- Mudancas devem ser pequenas e rastreaveis.

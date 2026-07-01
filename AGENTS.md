# VestLink - contexto para agentes

O contexto completo do VestLink fica no repositório externo:

https://github.com/igorcastro1010/vestlink-context

Antes de tarefas relevantes, leia no repo externo:

1. `SKILL.md`
2. `docs/contexto.md`
3. `docs/comandos-seguros.md`
4. `docs/estrutura-de-testes.md`
5. `docs/padrao-visual-ui-ux.md`

Comandos locais mínimos:

- `python manage.py check`
- `python manage.py test loja.tests.test_auth`
- `python manage.py test loja.tests.test_catalogo`
- `python manage.py test loja.tests.test_products`
- `python manage.py test loja.tests.test_leads`
- `python manage.py test loja.tests.test_dashboard`
- `python manage.py test loja.tests.test_billing`
- `python manage.py test loja.tests.test_infra`

Regras críticas:

- Nunca recriar `loja/tests.py`; use o pacote `loja/tests/`.
- Manter dark mode único.
- Não rodar `python manage.py test loja` sem necessidade.
- Não mexer em billing, auth ou estoque fora do escopo.
- Não versionar `.env`, logs, dumps, chaves, tokens ou dados sensíveis.
- Fazer commits isolados por intenção.

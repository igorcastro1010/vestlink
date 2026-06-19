# Protocolo do Cofre de Contexto

Este cofre é a primeira fonte de contexto do VestLink.

## Divulgação progressiva

1. Comece em `00 - Contexto/mapa-de-contexto.md`.
2. Leia o TL;DR da nota mais próxima da tarefa.
3. Pare quando o contexto for suficiente.
4. Abra os arquivos listados em `fontes` apenas para confirmar detalhes
   mutáveis, investigar bugs ou implementar alterações.

## Manutenção

- Toda nota deve ter frontmatter, TL;DR, fontes e data de revisão.
- Use `status: ativo`, `status: revisar` ou `status: arquivado`.
- Atualize a nota quando uma mudança alterar arquitetura, schema, fluxo,
  integração, decisão ou dívida técnica.
- Não copie blocos grandes de código. Registre comportamento, invariantes,
  riscos e ponteiros para o código.
- Não inclua credenciais, chaves, URLs com senha, tokens ou dados de usuários.
- Quando houver conflito, o código e a configuração de produção prevalecem;
  depois corrija a nota.

## Limite de leitura recomendado

- Pergunta simples: mapa + uma nota.
- Alteração localizada: mapa + nota do módulo + arquivos apontados.
- Mudança transversal: mapa + arquitetura + banco + integrações relacionadas.
- Auditoria: pode consultar o código amplamente, mas deve devolver os achados
  duráveis ao cofre.

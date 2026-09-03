# Investigação externa de conceitos

## Princípio

A internet expande a atenção do Diamond; não funciona como oráculo nem escreve
diretamente em conceitos ou memória.

```text
ConceptValidationReport
  -> gap pesquisável
  -> plano neutral-first
  -> EffectBroker
  -> adapter externo
  -> source_units não validados
  -> Cognitive Workspace / STAGED
  -> seleção UNVALIDATED_WORKSPACE_PROPOSAL
  -> /learn
```

O resultado externo só poderá contribuir para um selo depois de atravessar
`/learn` e sobreviver como proveniência de um cristal committed.

## Gaps pesquisáveis

O planner traduz apenas necessidades explícitas:

- `EXTERNAL_RECOGNITION`;
- `COMPETING_DEFINITIONS`;
- `UNCERTAIN_BOUNDARY`;
- `MISSING_RELATION`;
- `MISSING_VOCABULARY`.

Se o relatório não contém nenhum gap pesquisável, a blueprint não é criada.
Isto evita pesquisar apenas porque ainda existe internet disponível.

## Plano de queries

O plano é determinístico, limitado a uma a seis queries e segue:

1. características, funções e restrições sem revelar o nome;
2. relações constitutivas;
3. limites, alternativas e contraexemplos;
4. nome canónico e aliases, apenas no fim.

O executor rejeita planos fabricados que coloquem uma query reveladora do nome
antes do último lugar. Cada query possui finalidade e tipos de fonte
preferenciais.

## Efeito e permissões

A operação declara:

```text
effect:     internet.search
permission: internet.search:concept
```

Sem adapter ou permissão, o controller nega a execução antes de chamar a
operação. O adapter recebe o grant do plano e budgets explícitos.

O provider concreto inicial é `WikipediaConceptSearchAdapter`. O adapter
`AcademicLibrarySearchAdapter` cobre OpenAlex, Crossref, DOAJ e Internet
Archive através de APIs públicas read-only, devolvendo apenas source units
não validados e preservando `source_lineage`. CORE e Perseus continuam WIP
até existir um contrato de acesso sem credenciais nem ambiguidade de
scraping.

## Source units

Cada resultado válido torna-se `ConceptSourceUnit` com:

- query que o originou;
- título e fragmento limitado;
- URL HTTP(S);
- tipo de fonte;
- instante de retrieval;
- hash do conteúdo;
- autoridade fixa `UNVALIDATED_EXTERNAL_SOURCE`.

Resultados com query desconhecida, URL inválida ou estrutura malformada fazem a
operação falhar. Duplicados são removidos e o limite por query é imposto mesmo
que o adapter devolva mais.

Texto semelhante a instruções continua a ser apenas conteúdo externo. Ao entrar
no workspace torna-se uma nota `STAGED`, preservando a URL como proveniência e
sem alterar a autoridade da seleção.

## Estado executável

- Blueprint, manifesto e operação passam pelo controller normal.
- O `EffectBroker` medeia a única chamada externa.
- Replay canónico cobre quatro queries e quatro source units.
- Smoke test real com a Wikipédia portuguesa completou via HTTPS e encontrou a
  página “Automóvel” na query final pelo nome.
- O handoff pode ser executado por `ConceptSourceLearner`: todas as source
  units atravessam a blueprint normal de `/learn`, uma avaliação LLM
  sequencial e um `LearningCommit` atómico.
- Só cristais externos committed em estado `ACCEPTED` ou `PROVISIONAL` podem
  sustentar o relatório posterior de reconhecimento.
- O reconhecimento exige fecho estrutural e epistémico, pelo menos dois
  locators, evidência neutral-first para a definição e a query final do nome
  para reconhecimento.
- Um resultado suficiente cria uma nova versão do conceito com selos que
  referenciam simultaneamente `MEMORY_CRYSTAL` e `WEB_SOURCE`. A validade local
  anterior não é recalculada nem enfraquecida.
- Diversidade de fontes, cache, retries, saturação e adapters académicos
  continuam WIP.

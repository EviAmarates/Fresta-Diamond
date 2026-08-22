# Diamond — Cognitive Workspace

Estado: **folhas, revisões, hierarquia hash-bound, snippets, folha ativa,
representação canónica, decomposição determinística, avaliação LLM e
Gatekeeper isolado implementados; memória de produção ainda WIP**.

## Função

O Cognitive Workspace é a mesa de trabalho da LLM, não a memória principal nem
uma sandbox de execução de código hostil. Aproxima-se de um grafo de folhas com
backlinks onde a LLM pode:

- criar e rever rascunhos;
- dividir folhas em folhas-filhas;
- ligar fragmentos, cartões, conceitos, fontes e perguntas;
- experimentar papéis contextuais O1/O2/O3;
- formular hipóteses e contraexemplos;
- preparar sínteses e propostas;
- fazer checkpoint e retomar depois de sleep.

O workspace pode ser usado durante `/learn`, investigação prolongada, chat com
modo de trabalho explícito ou blueprints de manutenção limitada.

## Fronteira de autoridade

Conteúdo escrito no workspace não ganha autoridade apenas por existir:

```text
folha DRAFT
  -> objeto selecionado
  -> proposta interna de /learn
  -> Gatekeeper + três ordens + ónus epistémico
  -> ACCEPTED | DEFERRED | PROVISIONAL | QUARANTINED | Φ−
```

A LLM pode pedir `/learn`, mas não autorizar a própria promoção. O controller
deriva a cadeia, os brokers autorizam efeitos e os validadores calculam os
veredictos.

## Regra contra auto-confirmação

> Uma folha prova apenas que o workspace propôs ou registou algo. Não prova a
> verdade do conteúdo que ela própria contém.

Reler “Y causa X” numa folha cria uma atestação sobre o estado do workspace:
“a hipótese Y causa X foi proposta”. Para validar a relação causal, `/learn`
precisa de premissas, fontes, cartões, relações, testes e contraevidência que não
sejam meras cópias da mesma proposta.

Isto impede o ciclo vazio:

```text
eu escrevi -> eu reli -> logo confirmei
```

## Unidade de validação

Uma folha pode conter elementos com estados diferentes. `/learn` deve selecionar
claims, relações, hipóteses, perguntas ou conceitos específicos, não confirmar
ou rejeitar a folha inteira por bloco.

Exemplo:

```text
sheet:automoveis
  claim: motor transforma energia
  hypothesis: identidade funcional depende dos componentes
  relation: manutenção preserva continuidade
  open-question: quais componentes são constitutivos?
```

Cada elemento conserva scope, proveniência e ónus próprios.

## Folhas-mãe, filhos e evolução

Uma ligação `scope-child` aponta sempre para `revision_id + SHA-256`, nunca
apenas para o nome mutável de uma folha. A mãe funciona como índice: contém um
snippet curto e o link exato; o detalhe permanece no filho.

O filho pode evoluir normalmente para novas revisões. A mãe continua a provar
qual revisão foi realmente usada e `child_statuses`/`snippet_statuses` indicam
quando existe um head mais recente. Atualizar o índice exige uma nova revisão
da mãe; o passado não é reescrito.

## Decomposição sem perda

`SheetDecompositionService` divide deterministicamente um objeto que não cabe
num batch em folhas de conteúdo ordenadas. O corte respeita caracteres Unicode,
preserva todos os espaços e quebras de linha e verifica no fim que a concatenação
das folhas reproduz o SHA-256 do objeto original.

Se o número de filhos exceder o fan-out configurado, o serviço cria índices
intermédios até a raiz ficar limitada. Cada aresta aponta para uma revisão e
hash exatos; uma revisão posterior de um filho não altera a reconstrução antiga.
O limite declarado é apenas do conteúdo da folha: o chamador deve reservar
tokens adicionais para metadados e instruções da projeção de atenção.

A decomposição tem autoridade fixa
`UNVALIDATED_WORKSPACE_DECOMPOSITION`. Ela prova integridade, ordem e
proveniência, não a verdade semântica do conteúdo. Refinamento por O3/LLM pode
mais tarde propor fronteiras melhores sem substituir esta base reversível.

## Folha ativa

Um contexto de atenção pode declarar uma `active_sheet_ref` exata entre as suas
refs de workspace. A folha pode começar vazia. `revise_active_sheet` grava
primeiro a nova revisão da folha e depois cria uma nova revisão da atenção com
o ponteiro atualizado. A revisão anterior permanece resolvível pelo hash.

Sleep e retoma continuam ligados ao contexto, não à janela do modelo. Se a
folha ativa estiver entre os refs pendentes, o seu ponteiro acompanha a retoma;
um ref histórico nunca é substituído silenciosamente pelo latest.

O serviço central expõe `/workspace create`, `show` e `append`. Estes comandos
chamam fachadas da aplicação: podem iniciar uma folha vazia ou com uma nota,
resolver a revisão exata ligada ao contexto e acrescentar um elemento como nova
revisão. Não chamam a LLM, não validam o conteúdo e nunca reescrevem o passado.

## Duas representações auditáveis

Uma folha pode conter texto humano com `language` declarada e um elemento
`WORKING_REPRESENTATION` em `fresta-canonical@1`. A forma canónica explicita
objeto, objetivo, claims, dependências, proveniência, relações, constraints,
confiança heurística e perguntas abertas.

O codec JSON é canónico e possui round-trip exato. A autoridade permanece
`UNVALIDATED_WORKSPACE_REPRESENTATION`: confiança alta não valida uma claim.
Um dialeto auto-otimizado pela LLM continua apenas hipótese experimental e não
é necessário para ler ou recuperar estas folhas.

## Estados propostos

Dentro do workspace:

```text
DRAFT -> STAGED -> PROPOSED
```

Depois da pipeline de aprendizagem:

```text
ACCEPTED | DEFERRED | PROVISIONAL | QUARANTINED | Φ−
```

Uma aceitação cria um novo objeto versionado na memória apropriada. Não
transforma silenciosamente a folha original. Rascunho, sucessor, evidência,
decisão e exclusões ficam ligados pelo journal.

## Uso em manutenção

O modo idle nunca significa pensamento ilimitado sem objetivo. É uma blueprint
com objeto, critério, permissões e budget, por exemplo:

- rever `DEFERRED`;
- procurar contradições;
- decompor conceitos demasiado grandes;
- compactar folhas antigas;
- investigar um padrão Φ−;
- sugerir uma blueprint a partir de operações existentes.

Quando o objetivo fecha, para mesmo que reste budget. Quando o budget termina,
cria checkpoint e faz sleep sem fabricar conclusão.

## Camadas de memória

```text
journal arquivado   = passado imutável
checkpoint          = fronteira onde o trabalho parou
Cognitive Workspace = mesa mutável por revisão versionada
memória de atenção  = projeção ativa da mesa
cartões/conceitos   = conhecimento persistente validado
Φ−                  = exclusões e falhas preservadas
```

O primeiro lifecycle persistente dessa projeção está implementado separadamente
em [`ATTENTION-MEMORY.md`](ATTENTION-MEMORY.md). As folhas continuam a guardar
material provisório; a atenção apenas escolhe referências para um objetivo e
preserva contextos suspensos.

## Próxima implementação

1. ~~Persistir checkpoints e artefactos provisórios num workspace isolado.~~
2. ~~Adicionar contrato de `Sheet` e revisões imutáveis.~~
3. ~~Implementar backlinks e seleção de objetos internos.~~
4. ~~Criar uma proposta de blueprint `/learn` sobre um objeto selecionado.~~
5. ~~Garantir por teste que folhas nunca confirmam o próprio conteúdo.~~

## Corte executável atual

- `SheetRevision` conserva elementos tipados, âmbito, proveniência e papéis
  contextuais apenas nominados.
- Estados internos são monotónicos: `DRAFT -> STAGED -> PROPOSED`.
- Cada revisão aponta para a revisão anterior da mesma folha.
- `JsonlCognitiveWorkspace` mantém uma cadeia global SHA-256 e uma cadeia
  parental por folha; alteração, remoção intermédia ou reordenação ficam
  detetáveis.
- Backlinks atuais são derivados apenas das revisões mais recentes; o histórico
  continua consultável explicitamente.
- Uma seleção produz `artifact://workspace-selection@1` com autoridade fixa
  `UNVALIDATED_WORKSPACE_PROPOSAL`.
- A blueprint `workspace.learn-proposal` resolve a capability
  `learn.prepare-proposal@1` pelo controller normal e produz
  `artifact://learning-proposal@1`.
- A proposta explicita objetivos O1/O2/O3, Gatekeeper e ónus epistémico ainda
  necessários; a conclusão técnica desta preparação mantém os fechos
  estrutural, constitucional e epistémico sem avaliação.
- `learn.evaluate-proposal` faz uma única chamada semântica que propõe um bundle
  coerente com estrutura e classificação epistémica. Operações determinísticas
  separam depois os dois artefactos e os validadores independentes calculam os
  respetivos fechos.
- Chamadas adicionais não correm em paralelo: `learn.repair-evidence-bundle`
  recebe o bundle anterior e remainders concretos, com zero a duas tentativas
  limitadas pelo chamador.
- `CrystallizationGate` deriva por candidato `ACCEPTED`, `PROVISIONAL`,
  `DEFERRED` ou `QUARANTINED`. `PHI_MINUS` existe no contrato, mas não é usado
  para falhas finitas nem por defeito.
- `ATTESTATION`, `HYPOTHESIS` e `FORECAST` com ónus satisfeito cristalizam como
  `PROVISIONAL`, nunca como `CONFIRMED`.
- `JsonlLearningCrystalStore` chama internamente o Gatekeeper, liga versões do
  mesmo candidato e sela uma história append-only; não aceita estados fabricados
  diretamente pelo chamador.
- O workspace não contém estados `ACCEPTED` ou `CONFIRMED` e não possui método
  de promoção para memória.

Limites atuais: stores single-process, sem índice para histórias grandes, sem
branching/merge, sem decomposição semântica guiada por O3 e ainda sem integração
com memória de produção. Fecho
de uma `ATTESTATION` prova que a fonte relatou a afirmação, não a verdade
empírica do seu conteúdo.

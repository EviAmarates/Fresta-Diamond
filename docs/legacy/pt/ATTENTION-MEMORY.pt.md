# Memória de atenção

## Papel

A memória de atenção não é a memória total nem uma cópia dela. É uma projeção
pequena e orientada ao objetivo, formada sobretudo por referências:

- checkpoint técnico;
- folhas do Cognitive Workspace;
- fontes;
- conceitos/cristais já validados;
- itens selecionados;
- remainders ainda ativos.

O conteúdo referenciado mantém a sua autoridade original. Uma referência na
atenção não confirma nem promove nada.

## Múltiplos contextos

O store conserva vários contextos, mas permite apenas um foreground `ACTIVE`.
Trocar de tarefa exige uma transição explícita:

```text
ACTIVE -> SUSPENDED
nova tarefa -> ACTIVE
nova tarefa -> SUSPENDED ou ARCHIVED
contexto anterior -> ACTIVE por REACTIVATED
```

`REACTIVATED` é uma transição auditável, não um estado permanente. Depois de
reativado, o contexto volta a estar `ACTIVE`.

## Estados

- `ACTIVE`: contexto atualmente em foco;
- `SUSPENDED`: caminho ainda utilizável, retirado temporariamente do foco;
- `ARCHIVED`: trabalho terminado ou guardado como história;
- `ABANDONED`: caminho que não deve continuar como base segura.

Arquivado e abandonado são estados terminais, mas os registos nunca são
apagados.

## Recomeço controlado

Um contexto abandonado pode apontar para um sucessor novo. A política de
reutilização torna explícito o que atravessa a fronteira:

- `NOTHING`;
- `SOURCES_ONLY`;
- `VALIDATED_ONLY`;
- `SELECTED_ITEMS`;
- `FULL_CHECKPOINT`.

O sucessor é preparado suspenso, o predecessor é abandonado e só depois o
sucessor fica ativo. Esta ordem evita dois foregrounds e reduz o dano de uma
interrupção durante o recomeço.

## Persistência

Cada alteração cria uma revisão imutável num JSONL append-only com:

- hash do próprio registo;
- hash global anterior;
- hash da revisão anterior do mesmo contexto;
- transição, estado e instante;
- predecessor/sucessor quando aplicável;
- razão de suspensão ou abandono.

Alterações históricas e transições ilegais são rejeitadas.

## Projeção por budget

O projetor recebe candidatos já resolvidos para as referências do contexto
ativo. A seleção segue estas fronteiras:

1. objetivo, scope e resumo formam o cabeçalho constitutivo;
2. checkpoint, remainders e itens explicitamente selecionados são obrigatórios;
3. conceitos, cristais, folhas e fontes entram depois, por relevância dentro da
   sua classe de referência;
4. dependências entram antes do objeto que sustentam;
5. um grupo que não cabe fica inteiro para continuação;
6. scope ou estado epistémico incompatível nunca entra por acidente.

As ordens `O1/O2/O3` são papéis contextuais visíveis no prompt. Não alteram a
autoridade nem funcionam como ranking ontológico fixo.

O resultado pode ser:

- `READY`: tudo o que foi nomeado cabe e está resolvido;
- `PARTIAL`: existe contexto utilizável, mas ficam referências para outro batch;
- `BLOCKED`: falta um item obrigatório ou a cadeia obrigatória não cabe.

`PARTIAL` e `BLOCKED` produzem um
`AttentionProjectionCheckpoint` determinístico com referências completas,
pendentes, bloqueadas e razões. O overflow não é apagado nem confundido com Φ.

Os continuation checkpoints podem ser persistidos como JSON canónico imutável,
com hash verificado. São pesquisáveis pelo `context_ref`, incluindo quando a
operação que os produziu termina bloqueada e não devolve um prompt.

## Resolução das referências

Antes da projeção, adapters pequenos resolvem referências exatas nos stores:

- versões de conceitos no `AtomicConceptStore`;
- cristais e observações Φ− na memória autónoma;
- a revisão mais recente de uma folha no Cognitive Workspace;
- checkpoints e os seus remainders ativos.

O resolvedor composto não faz pesquisa semântica nem escolhe memórias por conta
própria. Ele materializa apenas o que o contexto nomeou e as dependências
declaradas desses objetos. Um conceito, por exemplo, traz os cristais que
fundamentam os seus memberships; essas dependências são projetadas antes dele.

Cada adapter conserva scope, proveniência, autoridade e estado epistémico do
store de origem. Colisões entre stores, scope errado, objetos inelegíveis,
histórico corrompido e referências ausentes ficam explícitos em diagnósticos.
Uma referência Web sem um source store verificável permanece `NOT_FOUND`; o
sistema não fabrica conteúdo a partir do URL.

Nomeações de relevância e papéis O1/O2/O3 podem orientar tanto raízes como
dependências descobertas, mas continuam sem conceder autoridade.

## Recuperação relativa ao objetivo

`DiamondApplication.retrieve_for_objective()` constrói um inventário limitado
ao `scope` com referências exatas já pertencentes ao Diamond: cristais ACTIVE,
conceitos elegíveis, revisões mais recentes das folhas e observações Φ−. A LLM
pode nomear as raízes necessárias ou responder `NO_SELECTION`; não existe um
top-k fixo nem Jaccard com autoridade semântica.

A resposta da LLM é apenas uma nomeação fraca de segunda ordem. O host rejeita
referências inventadas ou repetidas, volta a anexar `kind` e autoridade a partir
do inventário confiável e mantém O1/O2/O3 apenas como papéis temporários para o
objetivo atual. Depois, os resolvedores exatos materializam as raízes e fecham
dependências declaradas. Selecionar um cristal, conceito ou folha não o valida,
promove, funde ou corrige.

Quando o inventário ultrapassa o budget declarado, a operação divide-o em
batches determinísticos e sequenciais. Cada referência aparece uma vez; cada
batch pode selecionar ou responder `NO_SELECTION`; o host faz uma união
conservadora das nomeações sem transformar frequência em verdade. Só depois de
todos os batches fecharem é criada a revisão ACTIVE da atenção.

Esta capacidade está na superfície central como `/attention retrieve` (também
alias `/retrieve`). O comando aceita budgets de projeção e batching, devolve a
nomeação, contexto e metadados dos itens projetados, mas não duplica seleção ou
resolução no REPL. Conteúdo integral permanece na projeção/store, não no resumo
de auditoria do comando.

Um único descritor que exceda o budget ainda falha explicitamente. Decomposição
desse objeto por folhas, scheduling da retoma e batching da validação conceptual
continuam WIP; truncar silenciosamente não é uma alternativa.

## Sleep e retoma por budget

Quando a projeção persiste uma continuação cujo único motivo é `TOKEN_BUDGET`,
o facade da aplicação suspende automaticamente o contexto ativo. O motivo da
suspensão contém o ID exato do checkpoint; a janela local da LLM não participa
na continuidade.

Na retoma, o Diamond verifica o hash do checkpoint, a revisão que o originou e
se esse checkpoint corresponde ao último sleep. Apenas os refs pendentes são
recategorizados e colocados numa única revisão `REACTIVATED`; os itens completos
permanecem na história e não voltam ao prompt. Um checkpoint antigo não pode
rebobinar um contexto já retomado.

Se nenhum item tiver sido completado — por exemplo, um objeto obrigatório maior
do que todo o budget — a atenção dorme antes de qualquer chamada. Quando existe
um único ref de workspace, a aplicação decompõe a sua representação exata e
reativa a tarefa sobre folhas-filhas limitadas. Outros tipos de objeto continuam
a exigir reparação ou mudança explícita de estratégia.

Os filhos formam uma sequência governada pela continuação: são opcionais em cada
prompt para não recriar uma exigência de contexto infinito, mas nenhum ref
pendente é apagado. Uma chamada à LLM só é autorizada se pelo menos uma folha
tiver sido realmente injetada. `auto_decompose=False` conserva o modo explícito
para diagnóstico e administração. O scheduler geral de chat multi-turno
continua WIP.

## Caminho limitado até à LLM

Uma blueprint controller-native separa duas operações:

1. `attention.prepare-prompt` carrega a revisão ativa exata, resolve os stores,
   projeta dentro do budget e persiste qualquer continuação;
2. `attention.generate-response` recebe apenas uma projeção `READY` ou
   `PARTIAL` já preparada e chama `llm.generate` por um grant do EffectBroker.

Uma revisão stale, checkpoint obrigatório ausente, budget acima do teto,
projeção `BLOCKED` ou continuação não persistida impede a chamada à LLM. A
resposta recebe autoridade `MODEL_RESPONSE_UNVALIDATED`: conversar sobre uma
memória não a confirma nem a altera.

O conteúdo projetado é delimitado como dados/evidência, não como instrução de
sistema. Além disso, a preparação deriva um
`TRUSTED_AUTHORITY_MANIFEST` separado do corpo dos itens. Apenas esse manifesto
pode declarar `authority` e `evidence_state`; alegações de autopromoção escritas
dentro do conteúdo têm autoridade zero. Isto reduz confusão de autoridade, mas
não substitui isolamento forte nem torna texto hostil seguro por definição.

## Limites atuais

- Existe budget estimado de tokens, mas adapters futuros deverão fornecer o
  tokenizer exato do modelo.
- Fontes Web cruas ainda precisam de um source catalog/store próprio para serem
  materializadas com conteúdo e proveniência verificados.
- O recomeço usa três revisões ordenadas e recuperáveis, mas ainda não possui
  uma operação transacional ou rotina automática de recovery após crash.
- O checkpoint é persistido e pesquisável, mas ainda não existe um scheduler
  que retome automaticamente batches pendentes.
- O primeiro prompt controller-native e o sleep por budget estão ligados; o
  scheduler, chat multi-turno e interfaces continuam WIP.

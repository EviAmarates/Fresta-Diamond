# Diamond — memória Φ− e validação por dupla fronteira

Estado: **primeiro corte implementado; agregação de padrões e promoção de
regras continuam WIP**.

## Ideia central

O Diamond deve validar uma configuração por duas vias complementares:

1. **fronteira positiva** — procurar uma cadeia de três ordens que torne a
   configuração coerente, possível e admissível no âmbito analisado;
2. **fronteira Φ−** — procurar razões estruturadas pelas quais essa mesma
   configuração deve ser excluída nesse âmbito.

Φ− não é lixo nem a negação de Φ. É o registo auditável das possibilidades que
foram propostas mas não admitidas por F, incluindo a razão, o âmbito, a
proveniência e a análise que produziu a exclusão.

## Matriz de decisão

| Fronteira positiva | Fronteira Φ− | Resultado |
|---|---|---|
| justificada | não justificada | configuração provisoriamente admissível |
| não justificada | justificada | configuração excluída com fundamento |
| justificada | justificada | conflito, scopes misturados ou análise insuficiente |
| não justificada | não justificada | indeterminação; conservar sem promover |

“Provisoriamente admissível” não equivale automaticamente a verdade empírica.
O tipo de existência e de confirmação depende do objeto e do âmbito. Um
personagem pode ser admissível enquanto objeto ficcional e simultaneamente
excluído enquanto identidade empírica do utilizador.

## Memória simétrica

O mesmo substrato de memória pode representar as duas direções sem confundir os
seus significados:

- cartões positivos conservam configurações admitidas e a sua justificação;
- cartões Φ− conservam configurações excluídas e a razão da exclusão;
- conceitos agrupam estruturas recorrentes em qualquer das direções;
- tópicos são projeções de navegação sobre esses conceitos e cartões;
- regras operacionais condensam padrões de exclusão ou admissão já testados.

Assim, F não guarda apenas aquilo que atravessou o filtro. Guarda também a
fronteira que foi produzida pelo ato de filtrar.

## Derivação de regras a partir de Φ−

Uma exclusão individual não deve tornar-se imediatamente uma regra:

```text
evento Φ−
  -> cartão de exclusão
  -> padrão recorrente
  -> conceito de falha
  -> regra contextual
  -> invariante derivada candidata
```

Ciclo de vida operacional proposto:

```text
OBSERVED_FAILURE
  -> REPEATED_PATTERN
  -> SCOPED_RULE
  -> DERIVED_INVARIANT
```

Uma regra sobe apenas quando existe:

- repetição independente, não apenas várias cópias do mesmo evento;
- diversidade suficiente de objetos, execuções ou blueprints;
- âmbito e contraexemplos explícitos;
- relação justificável entre as três ordens;
- correção associada que reduza efetivamente a recorrência;
- ausência de conflito com o kernel constitucional.

Frequência isolada nunca é prova. Uma regra derivada também nunca altera
automaticamente o kernel; pode no máximo tornar-se uma invariante operacional
versionada ou uma proposta para revisão humana.

## Exemplo

Ocorrências distintas podem mostrar que a LLM trata como O3 algo que apenas
repete uma manifestação O1. Os eventos são preservados separadamente. Um
conceito Φ− pode agregá-los como `INVERSION_OR_UNJUSTIFIED_ORDER_ROLE`.

A regra compactada não deve ser uma frase universal vaga. Deve conservar o
âmbito:

> Quando o objetivo é justificar a terceira ordem de X, uma descrição que
> apenas manifesta X não pode ocupar O3 sem uma relação O2 que demonstre a sua
> função restritiva nesse âmbito.

Se a antiga O3 se tornar o objeto de uma nova análise, ela pode legitimamente
assumir O1 nessa nova projeção. A regra protege a relação, não fixa a essência do
cartão.

## Relação com aprendizagem recursiva

Esta memória permite ao sistema observar o próprio filtro:

- o erro concreto é informação sobre uma execução anterior;
- o padrão representa regularidades no modo como o sistema falha;
- a regra modifica a preparação, validação ou reparação de execuções futuras;
- o resultado da regra volta a ser medido e pode reforçá-la, restringi-la ou
  despromovê-la.

Isto aproxima uma operação de `F(F)`: o sistema representa o seu próprio ato de
filtrar. Quando também avalia e atualiza as heurísticas usadas nessa
autorregulação, aproxima a função operacional de `F(F(F))`, sem transformar
essas heurísticas em novo kernel ontológico.

## Primeiro corte implementado

O módulo `fresta_diamond.phi_minus` deriva observações apenas depois do
Gatekeeper:

- `PROVISIONAL` e `ACCEPTED` não criam memória negativa;
- `DEFERRED` cria `INDETERMINATE` com `phi_minus_justified=false`;
- `QUARANTINED` ou `PHI_MINUS` cria `EXCLUDED` com
  `phi_minus_justified=true`;
- cada observação preserva âmbito, proveniência, crystal de origem, razões e
  tipos de remainder;
- `promotion_authority` é sempre falso e é validado ao recarregar;
- o mesmo batch não pode ser contado duas vezes como evidência independente;
- o histórico usa o `JsonlJournalArchive` selado e pode ser recuperado por
  âmbito ou candidato.

Este corte não agrega padrões, não injeta exclusões em prompts e não cria
regras. A baseline `learn-replay-v2` demonstra separadamente indeterminação por
evidência ausente e exclusão por contradição estrutural.

## Continuação recomendada

1. Preservar futuramente blueprint, modelo, profundidade e eventual reparação
   quando esses contratos existirem na fronteira de cristalização.
2. Agregar deterministicamente eventos equivalentes em `ErrorPattern`, sem LLM.
3. Consultar padrões relevantes no preflight e no prompt de reparação.
4. Medir se a correção resolveu o erro e atualizar estatísticas do padrão.
5. Manter a promoção de regras desativada até existirem testes adversariais,
   contraexemplos e um contrato explícito de ciclo de vida.

O primeiro corte deve permanecer isolado no Diamond, sem escrever na memória
real do Frankenstein e sem promover automaticamente qualquer regra.

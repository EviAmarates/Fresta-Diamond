# Memória autónoma de aprendizagem

## Objetivo

O Diamond precisa de preservar o resultado de `/learn` sem depender da memória
do Frankenstein e sem separar artificialmente o que foi admitido do que foi
excluído pelo mesmo ato de filtragem.

Um `LearningCommit` contém, de forma inseparável:

- o `CrystallizationBatch` completo;
- cristais positivos, deferred e quarantined;
- observações da fronteira negativa;
- ligações entre cada observação Φ− e o cristal que a originou;
- proposta, batch e timestamps;
- `promotion_authority=false`.

## Persistência atómica

Cada commit segue:

```text
Gatekeeper + PhiMinusDeriver
  -> LearningCommit completo
  -> pending/<commit>.json.pending
  -> flush + fsync
  -> rename atómico
  -> commits/<commit>.json
```

Se a finalização falhar, o ficheiro completo permanece em `pending/`. Uma nova
instância valida o hash, o schema e todas as referências antes de executar
`recover_pending()`. A análise não é repetida nem reconstruída a partir de
texto.

Um proposal ID já committed não pode ser committed novamente. Isto impede que
uma única avaliação pareça evidência independente repetida.

## Recuperação segura

Persistência histórica e recuperação ativa são operações diferentes:

| Política | Estados recuperáveis |
|---|---|
| `ACTIVE` | `ACCEPTED`, `PROVISIONAL` |
| `FALLBACK` | anteriores + `DEFERRED` |
| `AUDIT` | todos, incluindo `QUARANTINED` e `PHI_MINUS` |

`ACTIVE` é o padrão. Um objeto existir no arquivo não lhe concede participação
num raciocínio normal.

`FALLBACK` é a futura via explícita para usar um deferred quando nenhum cartão
mais forte consegue sustentar a análise. A restrição permanece visível; esta
consulta não promove nem aumenta confiança por si própria.

`AUDIT` serve inspeção, reparação e estudo de Φ−. Nunca deve ser usado como
atalho de retrieval normal.

## Limitações honestas

- O store é single-process e experimental.
- Ainda não existe índice para históricos grandes.
- Não existe encriptação nem política de retenção.
- Não existe promoção automática, agregação Φ− ou atualização de confiança.
- Conceitos candidatos já podem ser derivados de cristais recuperáveis, mas
  ainda não participam no retrieval nem possuem validação contextual.
- Web e REPL ainda não estão ligados.
- O laboratório usa uma raiz temporária; nenhuma `data/` de produção participa.

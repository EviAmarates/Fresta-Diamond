# Integração externa de conceitos

## Fronteira

Pesquisa, aprendizagem e reconhecimento são operações diferentes:

```text
conceito VALIDATED
  -> pesquisa autorizada
  -> source units sem autoridade
  -> Cognitive Workspace
  -> /learn normal
  -> LearningCommit atómico
  -> relatório de reconhecimento
  -> selos MEMORY_CRYSTAL + WEB_SOURCE
  -> nova versão do conceito
```

Uma URL, um nome semelhante ou o autorrelato da LLM nunca atualizam diretamente
um conceito.

## Eixos independentes

- `local_fit`: adequação dos membros internos;
- `structural_state`: coerência estrutural interna;
- `definition_state`: suporte da definição, interno ou posteriormente
  corroborado externamente;
- `recognition_state`: reconhecimento externo do conceito/nome.

A investigação externa só revê os dois últimos eixos. Um conceito localmente
válido não se torna inválido só por ainda não ter reconhecimento externo.

## Regras executáveis

- O conceito de entrada tem de estar `VALIDATED` e ligado ao relatório interno
  que o validou.
- O artefacto de pesquisa tem de pertencer exatamente à versão analisada.
- O commit fornecido tem de ser igual ao commit canónico da memória autónoma;
  cópias forjadas são rejeitadas.
- Cada cristal externo preserva o `source_element_id`, o scope e a URL da source
  unit.
- `DEFERRED` produz indeterminação; `QUARANTINED` ou `PHI_MINUS` produz
  contestação; nenhum desses estados pode fingir suporte.
- Reconhecimento suportado exige pelo menos dois locators e a query do nome.
- Definição externa suportada exige pelo menos dois locators, duas queries e
  pelo menos uma query neutral-first.
- URLs diferentes só contam como independentes quando pertencem a famílias de
  fonte diferentes. Subdomínios do mesmo publisher não multiplicam evidência.
- A família é atualmente derivada do hostname por uma heurística conservadora e
  fica explícita no relatório para auditoria.
- A decisão de continuação é tipada: `CONTINUE_RESEARCH`, `STOP_SUFFICIENT`,
  `STOP_BUDGET` ou `REVIEW_CONFLICT`.
- Conflito tem prioridade sobre quantidade, diversidade e cobertura.
- Relatórios e versões são arquivados com hash. Nada recebe autoridade de
  promoção automática.

## Estado atual e limites

O ciclo está implementado em `concept_integration.py`; diversidade e stopping
policy estão em `source_policy.py`. Ambos estão cobertos por testes adversariais
e pela baseline `learn-replay-v8`. A chamada LLM da aprendizagem externa é
sequencial.

Ainda WIP: IDs editoriais verificados fornecidos pelos adapters, cache, retries,
reavaliação temporal, adapters académicos e análise semântica de conflitos que
tenham sobrevivido estruturalmente como alegações positivas.

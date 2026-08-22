# Laboratório de regressão do Diamond

## Objetivo

O laboratório permite alterar o Diamond e responder a uma pergunta concreta:

> Os invariantes importantes continuam iguais, melhoraram ou regrediram?

Ele pertence inteiramente a `diamond/testdata/`. Não reutiliza a memória de
produção nem o estado de testes do Frankenstein.

## Duas formas de executar o mesmo caso

### Replay determinístico

Usa uma resposta LLM gravada na fixture, mas atravessa a pipeline real:

```text
fixture
  -> Cognitive Workspace
  -> workspace.learn-proposal
  -> learn.evaluate-proposal
  -> OntologicalValidator
  -> EpistemicValidator
  -> CrystallizationGate
  -> projeção comparável
```

É rápido, repetível e adequado à suite automática. Não demonstra a qualidade
atual do modelo; demonstra que o Diamond continua a interpretar o mesmo input
segundo os mesmos contratos.

### Execução live

Substitui apenas o adapter replay pela LLM OpenAI-compatible local. Serve para
observar variação semântica e comparar o resultado atual com a mesma baseline.

```powershell
python scripts/run_benchmark.py --case automobile-attestation --live
```

A baseline não exige prosa idêntica. Compara apenas a projeção estável:

- eixos de fecho;
- remainders;
- estado e modo dos cristais;
- proveniência;
- fronteira documento/utilizador;
- fronteira negativa Φ− e a diferença entre indeterminação e exclusão;
- número de chamadas.

## Ciclo de trabalho

1. Antes da alteração, correr `python scripts/run_benchmark.py --all`.
2. Implementar uma mudança delimitada.
3. Correr os testes e novamente o benchmark.
4. Inspecionar cada diferença.
5. Corrigir regressões reais.
6. Se a diferença for uma melhoria pretendida, criar deliberadamente uma nova
   baseline; nunca substituir a anterior em silêncio.
7. Preservar o run como evidência do motivo da decisão.

## Comparação com o Frankenstein

A primeira comparação qualitativa direta está implementada em
`scripts/run_cross_benchmark.py`:

- a mesma fonte entra nos dois sistemas;
- cada sistema usa a sua própria pasta de dados;
- os outputs são normalizados num contrato comum;
- nenhum deles lê ou altera a memória do outro;
- o Frankenstein executa o comando central `/learn` em blueprint ativo;
- a baseline cruzada preserva concordâncias e divergências.

Neste corte, o Diamond recebe o seu grafo replay e o Frankenstein recebe uma
candidatura replay. Logo, a suite mede a capacidade das pipelines sobre as suas
representações nativas; ainda não mede paridade de prompt/modelo nem qualidade
de conceitos.

```powershell
python scripts/run_cross_benchmark.py --all
```

O primeiro resultado mostra:

- ambos preservam a fronteira documento/utilizador;
- ambos mantêm proveniência ausente como indeterminação;
- o Diamond exclui uma contradição estrutural O1=O3;
- o Frankenstein conserva essa candidatura como cartão `DEFERRED`;
- apenas o Frankenstein persiste cartões neste corte, porque a memória
  principal do Diamond continua desligada.

## Atualizar uma baseline

O runner não possui uma opção de promoção automática. Uma nova baseline deve
ter um ID novo, por exemplo `learn-replay-v2`, mantendo a anterior disponível
para auditoria. Depois atualiza-se `baseline_id` no manifesto.

Essa regra é intencional: o próprio sistema sob teste não tem autoridade para
declarar que o seu novo comportamento está correto.

`learn-replay-v1` permanece como fotografia anterior ao primeiro corte Φ−.
`learn-replay-v2` acrescenta a fronteira negativa e um caso adversarial de
colisão circular entre O1 e O3. `learn-replay-v3` acrescenta o commit atómico
da memória autónoma e prova que não ficam commits pendentes no caminho normal.
`learn-replay-v4` herda esses casos e acrescenta dois cristais que formam apenas
um conceito `CANDIDATE`: sem ordem intrínseca, validação ou promoção implícita.
As baselines podem declarar `extends`, mas os casos herdados continuam
imutáveis e auditáveis nos ficheiros anteriores.
`learn-replay-v5` acrescenta um caso derivado da mesma fonte: uma segunda
análise fechada cobre as sete partes necessárias com selos e cria a versão 2
`VALIDATED`, mantendo reconhecimento externo como `NOT_EVALUATED`.
`learn-replay-v6` acrescenta a investigação externa replay: quatro queries
neutral-first, uma chamada autorizada, quatro source units e staging no
workspace com handoff ainda não executado para `/learn`.
`learn-replay-v7` executa esse handoff: uma segunda avaliação sequencial produz
quatro cristais externos `PROVISIONAL`, confirma reconhecimento e definição
externa, cria quatro selos `MEMORY_CRYSTAL + WEB_SOURCE` e arquiva a versão 3 do
conceito sem alterar a sua validade local.
`learn-replay-v8` acrescenta a política de diversidade e paragem: quatro URLs
de quatro famílias editoriais satisfazem cobertura neutral-first e label,
produzindo `STOP_SUFFICIENT`. Subdomínios de uma só família já não podem
fabricar independência e conflito força sempre `REVIEW_CONFLICT`.

Na comparação cruzada, `cross-replay-v1` preserva a fase em que só o
Frankenstein persistia. `cross-replay-v2` mostra um cristal Diamond committed
por candidatura, mantendo a diferença de disposição epistémica visível.
O manifesto cruzado enumera explicitamente os quatro casos compatíveis; fixtures
Diamond-only, como o conceito multi-candidato, não entram por acidente na ponte
legada.

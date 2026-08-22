# Runner manual do Qwen

O runner liga uma LLM local ao caminho real do Diamond sem escrever em memória,
usar dados de produção ou importar o Frankenstein.

## Pré-requisitos

- servidor OpenAI-compatible ativo;
- `qwen/qwen3-14b` carregado;
- endpoint padrão `http://127.0.0.1:1234`.

## Execução

No PowerShell:

```powershell
cd C:\Users\User\fresta-novo\diamond
python scripts/run_qwen.py --object "Um automóvel transforma energia em movimento."
```

Também pode ler um ficheiro UTF-8:

```powershell
python scripts/run_qwen.py --file "C:\caminho\documento.txt"
```

Análise constitucional explícita:

```powershell
python scripts/run_qwen.py --object "A própria incompletude como condição de análise." --depth constitutional
```

Para mostrar a resposta original do modelo depois do veredito:

```powershell
python scripts/run_qwen.py --object "Objeto de teste" --debug
```

## Opções úteis

```text
--depth contextual|constitutional
--max-tokens 4000
--timeout 300
--repair-attempts 1
--base-url http://127.0.0.1:1234
--model qwen/qwen3-14b
--scope scope:nome-do-teste
```

`CONTEXTUAL` é o padrão. Não obriga a LLM a rederivar Φ/F.
`CONSTITUTIONAL` exige a fundamentação explícita e as duas direções.

## Segurança e autoridade

- modelo, host, token ceiling, objeto, scope e profundidade são fixados fora da
  resposta da LLM;
- a chamada atravessa `EffectBroker` como `llm.generate`;
- o modelo produz apenas uma proposta JSON;
- o decoder e o `OntologicalValidator` calculam o veredito;
- `advisory_model_closed` não possui autoridade;
- o runner não persiste cartões, conceitos ou configurações.

O fecho estrutural confirma a forma do grafo, não a verdade de todas as frases.
Proveniência inventada, scopes divergentes e relações semanticamente fracas
permanecem motivos para validação epistemológica posterior.

Uma proposta inválida não deve ser corrigida silenciosamente. O resultado e os
remainders podem alimentar futuramente uma operação de reparação separada e
limitada; a nova versão volta sempre ao mesmo validator.

O processo termina com código `0` quando existe fecho estrutural e `2` quando a
proposta executou mas não fechou estruturalmente. Falhas de servidor ou provider
aparecem nos remainders/erro do processo.

Quando V1 não fecha e `--repair-attempts` é maior que zero, o runner envia a
versão rejeitada e os seus remainders a uma operação de reparação separada.
Cada tentativa cria um novo artefacto; zero desativa reparação e três é o máximo
aceite pelo runner.

## Runner comparável

`scripts/run_qwen.py` e `scripts/run_learn_qwen.py` são ensaios manuais livres. Para repetir o
mesmo caso antes e depois de uma implementação, usar o laboratório:

```powershell
python scripts/run_benchmark.py --list
python scripts/run_benchmark.py --all
python scripts/run_benchmark.py --case automobile-attestation --live
```

Sem `--live`, o runner usa um bundle gravado e testa deterministicamente a
pipeline real. Com `--live`, chama o Qwen local e compara os invariantes com a
mesma baseline. Os runs ficam em `testdata/runs/`; nenhuma baseline é atualizada
automaticamente.

O desenho completo está em [`TEST-LAB.md`](TEST-LAB.md).

## Smoke test do serviço central de comandos

`run_commands.py` testa a futura fronteira comum de REPL/Web e exige uma pasta
de dados Diamond explícita:

```powershell
python run_commands.py --data-root .\local-command-data --command "/help"
python run_commands.py --data-root .\local-command-data `
  --command "/attention create --scope scope:smoke smoke"
```

O comando `attention turn` usa o mesmo host/modelo padrão deste documento. O
runner emite JSON, mostra `model_call_count`, estado de execução, remainders e
continuação. Uma chamada tentada que não produza `response` fica `INCOMPLETE` e
termina com código `3`, nunca como sucesso aparente.

## Turno limitado pela memória de atenção

Para testar separadamente o caminho
`atenção → resolução → projeção → controller → LLM`:

```powershell
python scripts/run_attention_qwen.py
```

Para forçar uma projeção `PARTIAL` e confirmar que a continuação é persistida
antes da chamada:

```powershell
python scripts/run_attention_qwen.py --unresolved-source
```

O runner usa dados temporários isolados. `model_called` e `model_call_count`
medem a invocação real do adapter, mesmo quando a operação não produz um
artefacto final. Conteúdo de workspace não pode declarar a própria autoridade;
o prompt usa um `TRUSTED_AUTHORITY_MANIFEST` derivado pelo projetor.

# Diamond — REPL persistente

Estado: **implementado como adapter fino sobre o serviço central de comandos**.

## Arranque

```powershell
cd C:\Users\User\fresta-novo\diamond
python run_repl.py --data-root .\local-repl-data
```

Por defeito usa `qwen/qwen3-14b` em `http://127.0.0.1:1234`. Os mesmos limites
do runner headless podem ser configurados:

```powershell
python run_repl.py --data-root .\local-repl-data `
  --model qwen/qwen3-14b --timeout 600 `
  --max-tokens 4000 --attention-tokens 7000 --response-tokens 2500
```

`/help` lista a superfície partilhada; `/exit` e `/quit` terminam apenas a
interface.

## Invariante arquitetural

O processo constrói uma única `DiamondApplication` e um único
`DiamondCommandService`. Cada linha é entregue a `execute_line()`; o REPL não
implementa `/learn`, atenção, módulos, blueprints ou memória.

```text
linha do utilizador
  -> DiamondRepl (apresentação)
  -> DiamondCommandService (comando canónico)
  -> DiamondApplication
  -> controller, módulos e stores
```

Isto preserva estado foreground, folhas, checkpoints, commits e decisões entre
comandos, sem depender da janela da LLM.

## Streams e erros

- Num terminal real existe prompt e JSON formatado.
- Por pipe, o prompt é omitido automaticamente; com `--compact`, cada resultado
  ocupa uma linha JSON limpa.
- Um comando inválido ou uma falha de adapter é apresentado com autoridade
  `REPL_PRESENTATION_ERROR_ONLY` e não destrói a sessão.
- `Ctrl+C` durante uma operação interrompe a linha atual e mantém o REPL ativo.
- `EOF`, `/exit` e `/quit` terminam de forma limpa.
- Um resultado `INCOMPLETE` continua a ser `INCOMPLETE`; o REPL não fabrica
  campos nem convergência para melhorar a apresentação.

O REPL não mantém um segundo histórico cognitivo. A persistência pertence aos
stores do Diamond; comandos digitados não são promovidos automaticamente para
memória.

## Limites atuais

- Ainda não existe Web, autenticação, streaming de tokens ou completion de
  comandos.
- A superfície só contém os comandos já centralizados.
- Cancelar uma chamada HTTP depende também de o adapter/servidor respeitar a
  interrupção; o REPL garante apenas que não transforma cancelamento em sucesso.

# Diamond — Shared Command Service

Estado: **serviço, runner headless e REPL persistente implementados; Web ainda não existe**.

## Função

`DiamondCommandService` é a única fronteira de comandos destinada às futuras
interfaces. Não reimplementa `/learn`, atenção, controller ou blueprints. Apenas:

1. resolve um nome canónico através do `CommandRegistry`;
2. valida e traduz argumentos de interface;
3. chama um método público da `DiamondApplication`;
4. devolve `CommandResult` com estado, payload, número real de chamadas e
   checkpoint de continuação;
5. converte o resultado para JSON através de `encode_command_result`.

Assim, REPL e Web não terão handlers cognitivos próprios:

```text
REPL ─┐
      ├─> DiamondCommandService ─> DiamondApplication ─> controller/stores
Web  ─┘
```

## Comandos atuais

| Comando | Efeito | Pode chamar LLM |
|---|---|---:|
| `/help` | Lista specs canónicas e aliases | não |
| `/learn TEXT` | Executa a pipeline persistente de aprendizagem | sim |
| `/chat start [--scope SCOPE] [--summary TEXT] [--budget N] [--batch-budget N] OBJECTIVE` | Cria sessão, retrieval/atenção e transcrito persistentes | sim, salvo inventário vazio |
| `/chat say [--budget N] SESSION_ID MESSAGE` | Persiste a mensagem e executa um turno de atenção | sim |
| `/chat status SESSION_ID` | Verifica binding, atenção e histórico selado | não |
| `/chat list` | Lista sessões sem carregar conteúdo das mensagens | não |
| `/attention create OBJECTIVE` | Cria contexto foreground | não |
| `/attention turn CONTEXT INSTRUCTION` | Projeta, responde, dorme/decompõe | sim |
| `/attention resume CHECKPOINT` | Retoma apenas refs pendentes | não |
| `/attention status [CONTEXT]` | Consulta contexto explícito ou foreground | não |
| `/attention retrieve [--scope SCOPE] [--budget N] [--batch-budget N] OBJECTIVE` | Seleciona refs exatas, atribui papéis contextuais e materializa atenção | sim |
| `/workspace create [--scope SCOPE] [--summary TEXT] [--title TEXT] [--content TEXT] OBJECTIVE` | Cria folha ativa versionada e novo contexto | não |
| `/workspace show CONTEXT_ID` | Lê a revisão exata atualmente ligada | não |
| `/workspace append [--kind KIND] [--summary TEXT] CONTEXT_ID CONTENT` | Acrescenta elemento numa nova revisão imutável | não |
| `/concept list [--scope SCOPE] [--state STATE] [--all-versions]` | Lista conceitos sem alterar o store | não |
| `/concept inspect [--version N] CONCEPT_ID` | Verifica e mostra uma versão exata | não |
| `/concept nominate [--scope SCOPE] [--crystals ID,ID] OBJECTIVE` | Nomeia ou recusa um candidato | sim |
| `/concept evaluate [--objective TEXT] CONCEPT_ID` | Propõe evidência e aplica validação determinística | sim |
| `/concept resolve [--objective TEXT] [--queries N] [--results N] CONCEPT_ID` | Avalia e só pesquisa/aprende se restar uma lacuna exata suportada | sim |
| `/module suggest --output-schema SCHEMA CAPABILITY OBJECTIVE` | Recusa ou arquiva um desenho não executável | sim, salvo provider exato |
| `/module proposals` | Lista decisões arquivadas | não |
| `/module inspect SUGGESTION_ID` | Inspeciona uma decisão e o seu preflight | não |

As mesmas operações podem ser chamadas estruturalmente por `invoke(name,
**arguments)`, evitando parsing textual no Web ou em módulos internos.

## Extensibilidade e autoridade

Um módulo pode registar um `CommandSpec`, handler e parser opcional sem editar o
serviço nem as interfaces. Colisões de nomes/aliases são rejeitadas. O handler
tem de devolver o mesmo `invocation_id` e comando canónico recebidos.

Uma invocação tem autoridade fixa `COMMAND_INVOCATION_ONLY`; a resposta usa
`COMMAND_RESULT_ONLY`. Isso prova apenas qual operação foi pedida e qual resultado
foi observado. Um comando não valida a verdade do conteúdo nem pode promover
memória fora dos Gatekeepers existentes.

`may_call_model` é metadado auditável para interfaces/debug. O resultado inclui
`model_call_count`, portanto reparações sequenciais não são escondidas.

## Limites atuais

- O REPL existe; ainda não existem servidor Web ou autenticação de utilizador.
- O parser textual é deliberadamente pequeno; integrações devem preferir
  `invoke()` com argumentos tipados.
- Retrieval e folha ativa usam agora comandos partilhados. Pesquisa geral e
  administração ainda não têm comandos. A pesquisa conceptual dirigida existe
  apenas dentro de `/concept resolve`, condicionada por um remainder validado.
- O chat usa atenção e workspace existentes. O histórico canónico vive no store
  `chat/`; não entra automaticamente em memória, perfil ou personalidade.
- Os comandos conceptuais textuais e `invoke("concept.*", ...)` chegam aos
  mesmos métodos públicos. `nominate` só cria `CANDIDATE`; `evaluate` aplica o
  validador determinístico. `resolve` reutiliza essa avaliação e deriva
  pesquisa → `/learn` → revisão → reavaliação apenas quando existe uma lacuna
  de selo explicitamente pesquisável.
- `/module suggest` não cria ficheiros de código, não instala e não ativa um
  módulo. O preflight da proposta também não é admissão real.
- Chaining de comandos deve nascer de blueprints/objetivos, não de sequências
  mágicas codificadas na interface.
- Erros levantam `CommandError`/erros de domínio; o futuro adapter decide o
  envelope HTTP ou apresentação terminal sem alterar a semântica.

## Próximo corte

O runner de um comando está em `run_commands.py`. Exige `--data-root` explícito,
constrói o adapter OpenAI-compatible e imprime apenas o codec JSON comum:

```powershell
python run_commands.py --data-root .\local-command-data --command "/help"
python run_commands.py --data-root .\local-command-data `
  --command "/learn Um automóvel transforma energia em movimento."
```

`INCOMPLETE` recebe exit code `3`; erros de parsing/configuração/runtime recebem
`2`. `COMPLETED`, `SUSPENDED` e `IDLE` recebem `0`. Uma tentativa de modelo sem
artefacto de resposta nunca é apresentada como conclusão.

O REPL fino está em `run_repl.py`: mantém o mesmo serviço em processo e apenas
renderiza o codec comum. O Web deverá reutilizar exatamente o mesmo serviço e
codec, depois de a cobertura dos comandos públicos estar estabilizada.

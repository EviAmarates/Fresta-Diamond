# Diamond — worklog canónico

Última consolidação: 2026-09-03.

Este documento acompanha exclusivamente o protótipo Diamond. O histórico anterior
foi preservado em [`LEGACY-WORKLOG-EXTRACT.md`](LEGACY-WORKLOG-EXTRACT.md).

## 2026-09-03 — Modos de resposta no percurso Web

- Foi distinguida a forma de resposta da autoridade: `conversation` produz uma
  resposta natural e `analysis` separa observações ancoradas, interpretações e
  perguntas abertas.
- O modo é apenas uma instrução bounded do turno de atenção; não altera
  retrieval, proveniência, budgets, Firewall, Gatekeeper, EffectBroker ou o
  estado aberto de Φ.
- O chat persistente existente continua a ser a única superfície de conversa;
  não foi criado um segundo chat. O selector do Web apenas escolhe o modo do
  turno investigativo e da continuação.

## 2026-09-03 — Primeiro percurso Web investigativo

- A caixa principal do Web passou a aceitar uma pergunta normal directamente,
  sem obrigar o utilizador a conhecer comandos slash.
- A pergunta atravessa a mesma fronteira central: retrieval relativo ao
  objectivo, plano/query bounded, pesquisa mediada, entrada normal em `/learn`,
  atenção persistente e resposta com continuidade.
- O novo comando `research`/`investigate` e o endpoint `POST /investigate`
  reutilizam o `DiamondCommandService`; o adapter Web não cria autoridade
  paralela nem promove fontes externas.
- O payload expõe fontes, `source_lineage`, autoridade, estado de execução,
  remainders, commits de aprendizagem, contexto de atenção e checkpoint quando
  existe. A resposta marca explicitamente `phi_open`.
- A experiência é dinâmica: o planner e o retrieval orientado pelas Três
  Ordens escolhem o que falta investigar dentro dos budgets; conflitos,
  alternativas e limites permanecem abertos.
- O primeiro smoke determinístico confirmou o percurso pergunta → query →
  fonte não validada → `/learn` → retrieval → atenção. O Web continua
  loopback-only e de desenvolvimento, não é deployment de produção.
- Verificação: **425 testes totais aprovados**.

## 2026-09-03 — Escalação consultiva da firewall

- A política de risco agora alimenta um serviço consultivo tipado no
  controller/application: `DENY` é `GRAVE`, cria primeiro um checkpoint
  imutável quando o store está disponível, depois regista a escalação e só
  então prepara a meta-análise consultiva.
- A meta-análise consultiva é persistida em `MetaMemoryStore` sem promover nem
  fechar Φ; o relatório mantém Φ aberto e o flag de integração pendente torna
  explícito o corte ainda não absorvido pelo controller.
- `QUARANTINE` continua a ser apenas revisão normal: não cria checkpoint nem
  pausa automática.
- A trilha de journal/proveniência agora inclui checkpoint e escalação
  consultivos, com arquivo JSONL selado quando disponível.
- Verificação: **422 testes totais aprovados**.

## 2026-09-03 — Bibliotecas externas não são autoridade

- As fontes académicas devem ser tratadas como bibliotecas externas: devolvem
  conhecimento tipado e matéria-prima com proveniência, não verdade nem pressão
  para concluir.
- Uma mini-lista inicial de fontes pode orientar o adapter, mas não deve ficar
  embutida como autoridade permanente. Depois do primeiro corte, a escolha deve
  ser derivada pelo objectivo e pela análise contextual O1/O2/O3.
- Toda a entrada externa atravessa a Firewall, o Gatekeeper, o controller e o
  `/learn`; a fonte pode ser rejeitada, mantida como hipótese, diferida ou
  preservada em Φ−. Nenhum resultado de biblioteca pode fechar Φ.
- A mini-lista funciona como heurística inicial, com a mesma dinâmica de
  filtragem da Firewall: as bibliotecas podem fornecer sinais tipados de risco e
  relevância, mas não podem escrever directamente em memória ou promover
  conhecimento.
- Padrões de exclusão/Φ− eventualmente comuns entre fontes devem ser
  observações para meta-análise e convergência, nunca pressão local para
  cristalizar, concluir ou fechar Φ.
- Se a Firewall sinalizar um risco grave e a análise O1/O2/O3 o confirmar como
  material para o objectivo, o controller deve criar primeiro um checkpoint
  imutável e suspender a continuação normal.
- Esse checkpoint abre uma meta-análise do episódio e dos padrões Φ−
  relacionados. A meta-análise é consultiva e pode reordenar investigação,
  filtros ou hipóteses; não promove memória, não transforma o alarme em
  verdade e nunca fecha Φ.

## 2026-09-03 — Runner question-only determinístico

- Foi implementado um contrato mínimo e determinístico para benchmark
  question-only: o Fresta persistente continua por episódios limitados e
  regista checkpoint/continuação, enquanto o baseline isolado recebe a mesma
  questão e os mesmos limites por chamada, sem persistência nem resume.
- A evidência externa permanece sempre não validada e preserva proveniência;
  o runner não invoca Φ-minus nem fecha Φ.
- O contrato usa adapters injectáveis para a proposta de queries e para a
  recolha de evidência, evitando dependência de HTTP vivo no milestone actual.

## 2026-09-03 — Auditoria de capacidades e journal persistente

- A auditoria confirmou que a facade `DiamondApplication` já compõe folhas,
  `/learn`, memória, Φ−, retrieval por objectivo, checkpoints, resume,
  conceitos e sugestões de módulos.
- A criação dinâmica de módulos não será assumida no benchmark sem prova de
  execução operacional; fica dependente da auditoria.
- Detectado e corrigido o wiring ausente dos journals: a aplicação passou a
  manter um `EventJournal` e `JsonlJournalArchive` persistentes, injectados em
  todos os controllers internos.
- O próximo corte é o protocolo question-only com pesquisa Web independente
  do baseline e pesquisa + memória/retrieval/continuação no Fresta.
- `docs/BENCHMARK-PROTOCOL.md` fixa a comparação closed-book/web-enabled,
  custos e regras de justiça. Regista também o limite actual: o adapter local
  ainda não expõe tool-calling Web genérico; o adaptador Wikipedia existente
  está preso ao fluxo de gaps de conceitos.
- Adicionado `DiamondApplication.research_objective()`: pesquisa bounded
  mediada pelo controller/EffectBroker, com fontes não validadas a entrarem no
  `/learn` normal.
- Adicionado o provider `llm-objective-research`: a LLM propõe queries num
  artefacto estruturado bounded, o controller valida o schema e só depois o
  `EffectBroker` pode executar a pesquisa. O runner question-only completo
  ainda não está concluído.
- Criado `AcademicLibrarySearchAdapter` para OpenAlex, Crossref, DOAJ e
  Internet Archive através de APIs públicas read-only. O adapter devolve apenas
  metadados/títulos como unidades `UNVALIDATED_EXTERNAL_SOURCE`, com
  `source_lineage` distinto por biblioteca.
- Adicionada cobertura mocked determinística para as quatro bibliotecas, com
  validação de URLs, filtragem de linhas malformadas e passagem de proveniência
  até ao pipeline de `source_units`.
- CORE e Perseus, bem como texto integral e snapshots, permanecem WIP até
  terem adapters e contratos de proveniência próprios sem ambiguidade de
  credenciais ou scraping.
- A pesquisa de objectivo passou a recuperar primeiro o estado relativo ao
  objectivo. A nomeação e a razão da recuperação são entregues à proposta da
  LLM como pista bounded; a pesquisa continua a atravessar Firewall,
  Gatekeeper, controller, EffectBroker e `/learn`, sem autoridade nova.
- O runner question-only determinístico e a CLI local foram ligados com
  isolamento explícito do baseline: o baseline não persiste nem faz resume; o
  Fresta pode continuar por episódios bounded e arquiva checkpoints. Ambos
  recebem apenas a pergunta e mantêm Φ aberto.
- A interface Web passa a explicar o Fresta como um companheiro de investigação
  semelhante a um Jarvis: memória persistente, pesquisa bounded e continuidade
  através de janelas limitadas, mas sem autoridade de oráculo ou decisão
  autónoma. A metáfora é apenas de UX; a ontologia continua a exigir
  proveniência, risco e validação.
- Regra de UX consolidada: **“O Fresta não inventa — investiga.”** Hipóteses e
  perguntas podem ser propostas, mas factos e fontes não são fabricados; a
  retenção continua dependente de proveniência, risco e validação.
- Criada uma política de severidade conservadora: apenas `DENY` é alarme
  `GRAVE` e requer checkpoint + meta-análise; `QUARANTINE` permanece `REVIEW`
  sem pausa automática. A política não fecha Φ e aguarda a integração do
  checkpoint/meta-analysis no controller.

## 2026-09-03 — Primeiro caso histórico curado

- Criado `roman-empire-fall-analysis` como primeiro caso histórico do benchmark.
- O caso usa três observações curadas e separadas sobre fragmentação
  administrativa, pressão fiscal-militar e conflito externo.
- A tarefa exige uma leitura multicausal e preserva cada fonte como
  `ATTESTATION`; não declara uma causa única nem concede promoção.
- O fixture foi ligado ao manifest e ao baseline replay `learn-replay-v8`.
- Este corte testa o `/learn` com material fornecido. A comparação
  closed-book/open-book e a matriz Qwen/OSS continuam por executar.

## 2026-09-03 — Lens explícita e guia ontológico inicial

- O kernel passou a nomear como **Lens** a operação de segunda ordem já
  realizada por Firewall, Gatekeeper, análise O1/O2/O3, Φ−, repair e
  revalidação; não foi criado um controlador paralelo.
- A saturação foi definida operacionalmente como perda contextual de
  recuperabilidade sob o objecto, scope, filtro, grounding e recursos actuais.
  Não é uma quantidade de informação, impossibilidade absoluta ou limiar
  produzido por score.
- A convergência meta-analítica pode fortalecer uma O3 específica do objecto
  quando há relações O2 independentes, contraexemplos tratados e revalidação.
  Essa O3 permanece contextual, revisável e nunca fecha Φ.
- Criado `docs/ONTOLOGY-GUIDE.md` como WIP para utilizadores, separado da
  autoridade constitucional do kernel.
- `MetaAnalysisReport` expõe agora uma avaliação Lens estruturada de
  recuperabilidade: `UNASSESSED`, `RECOVERABLE`, `AT_RISK`, `RESIDUAL` ou
  `CONTESTED`. `RESIDUAL` exige testemunho estrutural explícito e nunca é
  inferido apenas por score, timeout ou contagem de remainders.
- Verificação: **411 testes totais aprovados**.
- O smoke live com o modelo local actualmente carregado terminou sem promoção:
  respostas incompletas ficaram `DEFERRED` com `EXECUTION_INCOMPLETE`. O caso
  revelou uma falha no harness ao tentar construir um conceito com menos de dois
  crystals; o benchmark passou a devolver o resultado bounded em vez de lançar
  uma excepção não tipada.
- A documentação pública passou a definir o Fresta como uma camada
  **hipocampal para LLMs**: memória contextual persistente e suporte à
  observação activa através de janelas limitadas. É uma analogia arquitectural,
  não uma afirmação biológica, de consciência ou de autoridade independente.
- A definição foi precisada no sentido funcional da **cibernética de segunda
  ordem**: o Fresta observa e regula também o próprio processo de filtragem,
  memória, erro e correcção, sem se tornar uma autoridade independente.

## Objetivo

Construir uma instância limpa do Fresta Protocol por migração gradual: recuperar
apenas mecanismos demonstrados no Frankenstein, explicitar contratos e testar
cada corte antes de transportar a funcionalidade seguinte.

O Diamond não é ainda uma reescrita completa nem uma nova interface. É o runtime
limpo onde a arquitetura futura pode ser provada.

## Marcos concluídos

### Marco 0 — fronteira e arquitetura

- Separação entre laboratório Frankenstein e runtime Diamond.
- Contratos modulares definidos antes da migração de funcionalidades.
- Regra de conservação: copiar comportamento validado, não dívida histórica.

### Marco 1 — contratos e providers

- Contratos imutáveis, registry e controller desacoplado da interface.
- Providers substituíveis para testes determinísticos e futura LLM local.
- Resultado histórico: 6 testes Diamond; 187 testes totais.

### Marco 2 — execução derivada em DAG

- Dependências declarativas, ordenação topológica e deteção de ciclos.
- Validação anterior à execução.
- Ordem operacional separada da ordem ontológica relativa ao objeto.
- Resultado histórico: 10 testes Diamond; 191 testes totais.

### Marco 3 — fronteira de efeitos

- `EffectBroker` para mediar efeitos externos.
- Registos de intenção, execução e resultado.
- Modo de teste sem efeitos reais.
- Resultado histórico: 15 testes Diamond; 196 testes totais.

### Consolidação física

- Código, testes e documentação exclusivos reunidos em `diamond/`.
- Integração mínima na raiz limitada à descoberta de testes e ao link no README.
- Sem migração da `data/` real e sem alteração automática de dados do utilizador.

### Marco 4 — isolamento protegido e remainder canónico

- Teste AST impede imports diretos de `fresta` pelo package Diamond.
- Teste impede caminhos hardcoded de regresso ao Frankenstein.
- `Remainder` e `RemainderKind` substituem os nomes canónicos
  `PhiRemainder`/`PhiKind`.
- Coleções internas usam `remainders`; identificadores usam `remainder_id`.
- Aliases antigos permanecem apenas para leitura/importação durante a transição.
- Resultado: 19 testes Diamond; 200 testes totais.

### Marco 5 — testemunho ontológico executável

- Contratos imutáveis para manifestação O1, relação O2 forte, restrição O3,
  FILTER, custo excluído e fundamentação constitucional.
- Direções representadas por equivalências computacionais, sem depender dos
  símbolos escritos: `OPENNESS → FILTER → OBJECT` e reconhecimento inverso.
- `OntologicalValidator` separado do `PlanValidator` técnico.
- Fecho calculado pelo grafo; o booleano consultivo da LLM não tem autoridade.
- Testes adversariais cobrem testemunho vazio, FILTER ausente, direção invertida,
  custo vazio e evidência selecionada mas não utilizada.
- Resultado: 26 testes Diamond; 207 testes totais.

### Marco 6 — integração por artefacto

- Schema canónico `artifact://structural-evidence-graph@1`.
- Codec estrito entre payload JSON e contratos imutáveis.
- O provider produz evidência pelo dataflow normal, não por um booleano de fecho
  entregue diretamente ao controller.
- `OntologyEvaluator` integra relatórios no resultado e no `ClosureReport`.
- Payloads malformados permanecem visíveis como remainders.
- Ausência de artefacto mantém o fecho ontológico como `None`.
- Resultado: 29 testes Diamond; 210 testes totais.

### Marco 7 — profundidade constitucional condicional

- Corrigida a exigência excessiva de Φ/F em toda análise.
- `CONTEXTUAL` fecha relações pós-F sem percurso constitucional explícito.
- `CONSTITUTIONAL` exige a fundamentação completa quando o objetivo realmente
  quer chegar a esse nível.
- Fecho estrutural local e fecho constitucional deixaram de ser dependências
  booleanas obrigatórias.
- O schema transporta a profundidade escolhida pela blueprint.
- Resultado: 32 testes Diamond; 213 testes totais.

### Marco 8 — runner limitado do Qwen

- Adapter OpenAI-compatible sem dependências externas.
- Modelo, host, timeout e teto de tokens protegidos pela configuração e grant.
- Operação LLM produz o artefacto ontológico pelo caminho normal do controller.
- Scope, objeto e profundidade da blueprint substituem qualquer tentativa do
  modelo de os alterar.
- Parser tolera `<think>` e fences, mas exige um objeto JSON.
- Criado `run_qwen.py` para teste manual posterior, sem memória persistente.
- Resultado: 37 testes Diamond; 218 testes totais.

### Marco 9 — primeiros resultados live do Qwen

- Teste contextual completou todo o pipeline e fechou estruturalmente.
- O conteúdo mostrou justificações semanticamente fracas e alternativas não
  suportadas, apesar da forma válida.
- Teste constitucional inventou scopes e referências externas; o validator
  devolveu `INVALID_SCOPE`.
- Corrigido o bug que permitia fecho constitucional sobre estrutura local
  inválida.
- Prompt constitucional passou a definir OPENNESS/FILTER e a proibir fontes e
  observações inventadas.
- Segunda execução confirmou scope/proveniência corretos e detetou uma cadeia
  descontínua: a relação usava `c1`, enquanto o FILTER usava `c2`.
- O fecho constitucional permaneceu corretamente falso sobre a estrutura local
  inválida.
- Prompt passou a exigir o mesmo trio manifestação/restrição/custo entre O2 e
  seleção, sem retirar autoridade ao validator.
- Resultado: 39 testes Diamond; 220 testes totais.

### Marco 10 — reparação limitada e versionada

- Nova capability `three-orders.repair-evidence@1`.
- A operação recebe V1 e remainders e devolve uma nova versão completa.
- Cada revisão conserva `parent_artifact_id` e número da tentativa.
- Runner limita explicitamente reparações entre zero e três, com uma por padrão.
- O mesmo validator reavalia todas as versões; a LLM não marca a reparação como
  concluída.
- Primeiro ensaio live fechou em V1 e não fez uma chamada desnecessária.
- O conteúdo ainda confundiu parcialmente incompletude constitucional com
  linguagem epistémica, confirmando a necessidade da próxima camada.
- Resultado: 41 testes Diamond; 222 testes totais.

### Marco 11 — evidência epistémica por modo de afirmação

- Criado o schema independente `artifact://epistemic-evidence-graph@1`.
- Afirmações declaram `OBSERVATION`, `ATTESTATION`, `DERIVATION`, `HYPOTHESIS`,
  `FORECAST` ou `INVARIANT`.
- Eventos de evidência separam ator, localizador, linhagem, contexto, método,
  tempo, âmbito e direção de suporte ou contradição.
- O sujeito da afirmação, o ator da fonte e o proprietário da memória permanecem
  referências diferentes.
- `EpistemicValidator` aplica ónus mínimos próprios de cada modo e não aceita
  cópias da mesma linhagem como confirmações independentes de uma invariante.
- Contraevidência viva, evidência não utilizada, cruzada entre claims,
  malformada ou fora do âmbito permanece como remainder.
- `EpistemicEvaluator` calcula apenas `epistemic_closed`; não altera os eixos
  estrutural ou constitucional.
- Hipóteses podem satisfazer o ónus de serem hipóteses testáveis sem se tornarem
  observações ou cartões confirmados.
- Resultado: 49 testes Diamond; 230 testes totais.

### Marco 12 — journal de execução append-only

- Criado `EventJournal` in-memory com sequência monotónica, IDs gerados,
  timestamp, correlação por plano e causalidade explícita.
- Payloads são snapshots profundamente imutáveis; alterações posteriores no
  objeto do chamador não reescrevem o evento.
- Causas desconhecidas e IDs duplicados são rejeitados.
- Controller regista proposta/validação do plano, autorização, avaliações
  ontológica e epistémica e resultado final do objetivo.
- Runtime regista início, output e falha das operações.
- `EffectBroker` regista pedido, commit e rejeição sem copiar argumentos
  sensíveis do adapter.
- Um journal partilhado mantém ordem global, mas cada `ControllerResult` recebe
  apenas os eventos da sua execução.
- O journal permanece opcional, volátil e sem ligação à `data/` real.
- Resultado: 56 testes Diamond; 237 testes totais.

### Marco 13 — arquivo histórico selado

- Criado `JsonlJournalArchive`, ativado apenas por injeção explícita.
- Execuções são seladas em segmentos `fresta://journal-segment@1` com uma única
  correlação e sequências contíguas.
- Cada corpo JSON canónico recebe SHA-256 e referencia o hash do segmento
  anterior.
- A leitura revalida toda a cadeia e rejeita adulteração histórica.
- Consulta por correlação recupera apenas os segmentos pedidos; o arquivo não
  entra automaticamente na atenção.
- O controller arquiva somente os eventos produzidos pela chamada atual.
- Falha de arquivo conserva outputs já produzidos, abre a convergência
  operacional, acrescenta `EXTERNAL_UNCERTAINTY` e não repete efeitos.
- A implementação permanece single-process e sem escrita na `data/` real.
- Resultado: 62 testes Diamond; 243 testes totais.

### Marco 14 — budget finito, checkpoint e resume

- Criado `ExecutionBudget`; o primeiro relógio conta operações concluídas por
  episódio.
- Budget zero pausa antes do primeiro nó; budget esgotado nunca significa
  convergência, verdade ou PHI.
- `RuntimeCheckpoint` conserva plano, fronteira concluída/pendente, artefactos
  intermediários, outputs, remainders e linhagem de checkpoints.
- Runtime emite `CHECKPOINT_CREATED` e `EXECUTION_PAUSED`.
- `DiamondController.resume()` recebe novo budget, emite
  `EXECUTION_RESUMED`, revalida providers e reautoriza efeitos.
- Nós concluídos não são repetidos.
- Segmentos arquivados da pausa e do resume partilham correlação e cadeia de
  hashes; o checkpoint devolvido referencia o hash da sua pausa.
- Teste de três operações com budget unitário conclui em três episódios, cada
  operação exatamente uma vez.
- Provider removido durante sleep deixa a continuação aberta e não cria
  fallback.
- Resultado: 68 testes Diamond; 249 testes totais.

### Marco 15 — workspace persistente de checkpoints

- Criado schema `fresta://runtime-checkpoint@1` e codecs estritos para plano,
  budget, fronteira, artefactos, outputs e remainders.
- `JsonCheckpointStore` só cria diretório quando uma pausa configurada é
  realmente persistida.
- Cada checkpoint é imutável por ID e selado com SHA-256.
- Overwrite, adulteração, path traversal e payload malformado são rejeitados.
- Persistência exige archive injetado e conserva o hash do segmento histórico.
- Teste simulou restart com novos controller, journal, archive e store; o resume
  executou apenas os nós pendentes.
- Falha de persistência mantém a fronteira volátil, abre convergência e emite
  `CHECKPOINT_PERSISTENCE_FAILED`.
- Nenhuma escrita foi ligada à `data/` real.
- Resultado: 71 testes Diamond; 252 testes totais.

### Marco 16 — admissão anti-entropia executável

- `verify()` deixou de ser uma mudança vazia de estado e passou a derivar um
  relatório imutável de admissão.
- A origem e a evidência de descoberta pertencem ao loader confiável, não ao
  manifesto candidato.
- Módulos comunitários exigem proveniência e digest SHA-256; operações com
  efeitos exigem permissões e modos de falha declarados.
- Famílias constitucionais protegidas de kernel, validator, trust, journal,
  proveniência e escrita direta de memória são rejeitadas em qualquer origem.
- Rejeição cria `POLICY_VIOLATION`, estado `REJECTED`, bloqueia handlers e fica
  observável no journal sem copiar o pacote candidato.
- O limite continua explícito: isto não é isolamento de Python hostil nem
  validação de assinatura.
- Resultado: 80 testes Diamond; 261 testes totais.

### Marco 17 — folhas cognitivas revisionadas

- Criados contratos imutáveis para elementos, ligações, revisões, backlinks e
  seleções do workspace.
- Cada elemento preserva o seu próprio tipo, scope, proveniência e nomeações de
  ordem contextual.
- Revisões são append-only, contíguas, ligadas ao pai mais recente e limitadas
  aos estados internos `DRAFT`, `STAGED` e `PROPOSED`.
- O store JSONL verifica cadeia SHA-256 global e cadeia parental de cada folha.
- Backlinks são derivados das ligações; por defeito refletem apenas as revisões
  atuais, mantendo consulta histórica explícita.
- Seleções saem como artefactos `UNVALIDATED_WORKSPACE_PROPOSAL`; não existe API
  de auto-confirmação ou promoção de memória.
- Resultado: 88 testes Diamond; 269 testes totais.

### Marco 18 — ponte do workspace para `/learn`

- Uma seleção pode agora formar um `WorkspaceLearnRequest` com blueprint,
  objetivo e inputs tipados para o controller normal.
- `workspace.learn-proposal` pede uma capability; não fixa providers nem cria
  uma cadeia paralela de comandos.
- O provider determinístico de intake passa pela admissão anti-entropia.
- O output mantém cada candidato como `UNVALIDATED`, conserva a proveniência e
  declara os trabalhos O1/O2/O3, Gatekeeper e ónus epistémico ainda necessários.
- Fecho técnico do intake não fabrica fecho estrutural, constitucional ou
  epistémico e nunca concede promoção.
- A correção revelou e fechou uma dívida transversal: `Artifact.payload` é
  agora profundamente imutável, incluindo objetos e listas aninhados.
- Resultado: 94 testes Diamond; 275 testes totais.

### Marco 19 — primeira avaliação LLM do `/learn`

- Uma única chamada ao modelo produz estrutura e avaliação epistémica na mesma
  leitura; operações determinísticas separam depois os dois eixos.
- Os validadores continuam independentes e não consultam os booleanos do
  modelo.
- Scope, objeto, candidatos, sujeitos e proveniência são restaurados ou
  limitados fora da autoridade da LLM.
- Proveniência documental não se transforma em identidade do utilizador e
  hipóteses mantêm o seu modo.
- Outputs semanticamente incompletos continuam como artefactos reparáveis em
  vez de desaparecerem numa falha técnica.
- Reparação é sequencial, limitada e recebe o bundle anterior mais os
  remainders determinísticos; não existem duas interpretações paralelas cegas.
- Ensaio live com `qwen/qwen3-14b` fechou estrutura e `ATTESTATION` numa chamada,
  em cerca de 45 segundos. Não avaliou o eixo constitucional nem promoveu
  memória.
- A linguagem estrutural ainda foi vaga, demonstrando que fecho formal e
  qualidade semântica continuam distintos.
- Resultado: 101 testes Diamond; 282 testes totais.

### Marco 20 — Gatekeeper determinístico de cristalização

- O Gatekeeper recebe a proposta original e os dois relatórios, decidindo um
  estado por elemento em vez de validar a folha inteira.
- Atestações, hipóteses e previsões fechadas tornam-se `PROVISIONAL`;
  evidência em falta torna-se `DEFERRED`; contradições e adulteração tornam-se
  `QUARANTINED`.
- `ACCEPTED` exige um modo forte com o respetivo ónus satisfeito.
- Não existe estado `CONFIRMED`; `PHI_MINUS` fica reservado para exclusão
  negativa explícita futura.
- O store isolado não recebe decisões prontas: executa o Gatekeeper, cria
  linhagem por candidato e sela cada batch numa cadeia SHA-256.
- Nenhum caminho foi ligado à `data/` de produção.
- Resultado: 108 testes Diamond; 289 testes totais.

### Marco 21 — laboratório isolado de regressão

- Criada `diamond/testdata/`, sem dependências de `../data/` ou
  `../data-tests/` do Frankenstein.
- Fixtures imutáveis são verificadas por SHA-256 antes de entrar na pipeline.
- O modo replay atravessa o intake, controller, avaliação estrutural e
  epistémica e Gatekeeper reais, substituindo apenas a chamada externa.
- O modo live usa os mesmos casos com a LLM local.
- Baselines guardam invariantes e nunca são atualizadas automaticamente.
- Runs novos são arquivados individualmente para preservar a história da
  comparação.
- A primeira baseline cobre atestação documental, fronteira de identidade
  ficcional/utilizador e rejeição de proveniência inventada.
- Resultado: 114 testes Diamond; 295 testes totais; 3/3 casos replay iguais à
  baseline `learn-replay-v1`.

### Marco 22 — primeiro corte executável de memória Φ−

- Criado contrato imutável `PhiMinusObservation`.
- Separada exclusão justificada de indeterminação: `DEFERRED` nunca se torna
  automaticamente uma proibição.
- O arquivo reutiliza o journal JSONL selado e recupera observações por âmbito
  ou candidato.
- Repetir o mesmo batch é recusado para não fabricar repetição independente.
- Toda observação tem `promotion_authority=false`; não existem agregação,
  regras automáticas ou alterações ao kernel.
- Preservada `learn-replay-v1` e criada `learn-replay-v2`, incluindo um caso de
  contradição estrutural que produz uma exclusão Φ− real.
- Resultado: 120 testes Diamond; 301 testes totais; 4/4 casos replay iguais à
  baseline `learn-replay-v2`.

### Marco 23 — primeira comparação Diamond ↔ Frankenstein

- Criado bridge fora do package `fresta_diamond`, preservando a autonomia do
  Diamond.
- O Frankenstein executa o comando central `/learn` em blueprint ativo e numa
  pasta temporária vazia por caso.
- A extração e a proposta Diamond usam replay determinístico; nenhuma rede ou
  memória de produção participa.
- O contrato normalizado compara disposição, fronteira de identidade, estado
  epistémico, persistência e Φ− sem fingir igualdade de schemas.
- `cross-replay-v1` preserva os resultados atuais: 1 caso com concordância de
  disposição e 3 divergências explícitas.
- A divergência principal é útil: o Diamond exclui contradição O1=O3; o
  Frankenstein persiste a candidatura como `DEFERRED`.
- Resultado: 120 testes Diamond; 307 testes totais; 4/4 comparações iguais à
  baseline `cross-replay-v1`.

### Marco 24 — memória autónoma por commit atómico

- Criado `LearningCommit`, contendo o batch de cristais e a fronteira Φ−
  derivada da mesma avaliação.
- Escrita file-per-commit usa preparação, `fsync` e finalização por rename
  atómico.
- Uma falha de finalização deixa um commit completo em `pending/`; outra
  instância pode validá-lo e recuperá-lo sem repetir a LLM ou o Gatekeeper.
- Proposal IDs já committed não podem ser contados novamente.
- Retrieval normal devolve apenas `ACCEPTED/PROVISIONAL`; `DEFERRED` exige
  `FALLBACK`; exclusões exigem `AUDIT`.
- `learn-replay-v3` e `cross-replay-v2` preservam as baselines anteriores e
  tornam a nova persistência observável.
- Resultado: 129 testes Diamond; 316 testes totais; 4/4 casos em cada baseline
  atual.

### Marco 25 — fundação nativa de conceitos candidatos

- Criados contratos Diamond para conceitos, assinaturas intensionais,
  pertenças, aliases e ligações pai–filho, sem armazenar ordens intrínsecas.
- O builder aceita apenas cristais committed recuperáveis pela política
  escolhida; `DEFERRED` exige `FALLBACK`.
- Conceitos exigem pelo menos dois membros distintos e uma característica
  intensional.
- O store preserva versões e aliases, aceita múltiplos pais conhecidos e
  rejeita ciclos.
- Estados futuros já estão tipados, mas a promoção permanece fail-closed:
  `VALIDATED` e `CRYSTALLIZED` só serão aceites quando existir uma operação de
  validação contextual.
- `learn-replay-v4` acrescenta a fixture canónica de automóvel com dois cristais
  e resultado exclusivamente `CANDIDATE`.
- O runner cruzado passou a obedecer à allowlist do seu próprio manifesto; a
  fixture Diamond-only não é enviada ao Frankenstein.
- Resultado: 139 testes Diamond; 326 testes totais; 5/5 casos na baseline
  `learn-replay-v4` e 4/4 na baseline cruzada `cross-replay-v2`.

### Marco 26 — validação interna selada de conceitos

- Implementado `DerivationSeal` por característica, relação, restrição,
  exclusão ou pertença, com origem tipada, contribuição, análise e digest.
- O `ConceptValidator` recebe grafos completos e reutiliza os validadores
  estrutural e epistémico; nunca aceita apenas `closed=true`.
- O relatório separa ajuste local, estrutura, definição e reconhecimento
  externo.
- Evidência completa cria uma nova versão `VALIDATED`; lacunas preservam o
  `CANDIDATE`; contraevidência cria `CONTESTED`.
- Relatórios são arquivados com hash antes da versão promovida. O método público
  do store continua fail-closed para validações fabricadas.
- Uma fonte web solta não entra. Depois de `/learn`, a proveniência externa de
  um cristal committed pode participar com tipo `WEB_SOURCE`.
- `learn-replay-v5` preserva v4 e acrescenta a validação do conceito automóvel.
- Resultado: 147 testes Diamond; 334 testes totais; 6/6 casos Diamond e 4/4
  casos cruzados coincidem com as baselines atuais.

### Marco 27 — investigação conceptual externa mediada

- Remainders conceptuais passam a gaps pesquisáveis com tipo e alvo explícitos.
- O planner pesquisa características antes do nome e inclui relações,
  fronteiras e contraexemplos.
- `workspace.research-concept` usa o controller normal e exige o efeito
  `internet.search` com permissão `internet.search:concept`.
- Resultados são limitados, deduplicados, selados por hash e marcados
  `UNVALIDATED_EXTERNAL_SOURCE`.
- Texto externo semelhante a instruções permanece conteúdo de uma nota; não
  altera permissões nem promoção.
- O workspace recebe as notas como `STAGED` e prepara uma seleção para `/learn`.
- Criado adapter opcional da Wikipédia com TLS verificado e trust store do
  Windows. Smoke test real encontrou “Automóvel” sem tocar na data do projeto.
- `learn-replay-v6` cobre sete casos Diamond; o bridge Frankenstein permanece
  conscientemente nos quatro casos compatíveis.
- Resultado: 155 testes Diamond; 342 testes totais; 7/7 casos Diamond e 4/4
  casos cruzados coincidem com as baselines atuais.

### Marco 28 — reconhecimento externo depois de `/learn`

- As source units da pesquisa entram agora na blueprint normal de `/learn` e
  são persistidas por `LearningCommit`; não existe atalho Web → conceito.
- O validador de reconhecimento confere o commit fornecido contra a memória
  autónoma e rejeita perda/invenção de source units, URL ou scope.
- Reconhecimento e definição externa são avaliados separadamente da validade
  local. Evidência `DEFERRED` não suporta; `QUARANTINED`/`PHI_MINUS` contesta.
- Evidência suficiente cria uma versão nova com selos emparelhados
  `MEMORY_CRYSTAL + WEB_SOURCE`; relatórios insuficientes ficam arquivados sem
  criarem versão.
- A baseline `learn-replay-v7` cobre o ciclo completo e mantém a chamada externa
  da LLM sequencial.
- Resultado: 161 testes Diamond; 348 testes totais; 8/8 casos Diamond e 4/4
  casos cruzados coincidem com as baselines atuais.

### Marco 29 — diversidade de fontes e paragem limitada

- Criada uma política tipada que mede cobertura sem afirmar verdade semântica.
- URLs de subdomínios do mesmo publisher contam como uma família; a fixture
  canónica passou a usar quatro famílias realmente distintas.
- Cobertura suficiente exige quantidade mínima, diversidade editorial, query
  neutral e query do nome.
- A política devolve `CONTINUE_RESEARCH`, `STOP_SUFFICIENT`, `STOP_BUDGET` ou
  `REVIEW_CONFLICT`; parar significa objetivo satisfeito ou budget esgotado,
  nunca totalidade.
- Conflito tem prioridade sobre suficiência e não pode ser apagado por maioria.
- `learn-replay-v8` sela a nova projeção.
- Resultado: 168 testes Diamond; 355 testes totais; 8/8 casos Diamond e 4/4
  casos cruzados coincidem com as baselines atuais.

### Marco 30 — lifecycle multi-contexto da atenção

- Implementado store append-only para múltiplos contextos, com apenas um
  foreground `ACTIVE`.
- `SUSPENDED` preserva um caminho retomável; `ARCHIVED` preserva trabalho
  fechado; `ABANDONED` conserva uma linha que já não é base segura.
- Reativação é uma transição para `ACTIVE`, registada no histórico.
- O recomeço controlado prepara um sucessor limpo e transporta apenas o que a
  política autoriza: nada, fontes, validados, seleção explícita ou checkpoint
  completo.
- A atenção guarda referências e autoridade `ATTENTION_PROJECTION_ONLY`; não
  copia nem confirma memória principal.
- Hash global, parent hash e transições terminais protegem o histórico.
- Resultado: 178 testes Diamond; 365 testes totais; as baselines v8 e cross-v2
  permanecem integralmente verdes.

### Marco 31 — projeção limitada e fechada por dependências

- O contexto ativo pode agora ser projetado para um budget estimado de tokens.
- Objetivo/resumo são constitutivos; checkpoint, remainders e seleção explícita
  são obrigatórios.
- Conceitos, cristais, folhas, fontes e Φ− preservam estado, autoridade,
  proveniência e papéis contextuais.
- Dependências entram antes do objeto e como grupo indivisível dentro do
  budget.
- Resultado `PARTIAL` continua utilizável; `BLOCKED` impede injeção insegura.
- Overflow produz checkpoint determinístico para batches posteriores.
- Resultado: 187 testes Diamond; 374 testes totais; as baselines v8 e cross-v2
  permanecem verdes.

### Marco 32 — resolução exata da atenção

- Adicionados adapters separados para conceitos versionados, cristais,
  observações Φ−, folhas cognitivas, checkpoints e remainders ativos.
- O composite apenas resolve referências exatas do contexto e dependências
  declaradas pelos objetos; não faz retrieval semântico escondido.
- Memberships de conceitos materializam os cristais de suporte como
  dependências, preservando fecho antes da projeção.
- Scope, proveniência, autoridade e estado epistémico permanecem ligados ao
  store de origem.
- Ausência, scope errado, inelegibilidade, colisão entre stores e erro de
  integridade são diagnósticos explícitos. Falha obrigatória bloqueia prompt.
- URLs sem source store ficam por resolver e nunca são transformados em
  conteúdo inventado.
- Resultado: 194 testes Diamond; 381 testes totais; nenhuma chamada LLM e
  nenhuma alteração às baselines v8/cross-v2.

### Marco 33 — continuação durável e primeiro turno controller-native

- O continuation checkpoint passou a ter store JSON imutável, hash verificado
  e pesquisa por revisão do contexto.
- A blueprint de atenção deriva duas operações: preparação determinística e
  geração LLM autorizada pelo EffectBroker.
- A preparação verifica revisão exata, teto de tokens, resolução, projeção e
  persistência antes de permitir a chamada.
- Contexto stale, `BLOCKED`, budget excessivo ou continuação não durável deixam
  o contador de chamadas a zero.
- `READY` segue diretamente; `PARTIAL` só segue depois de preservar o trabalho
  pendente. A resposta continua explicitamente não validada.
- Criado `run_attention_qwen.py` para ensaio isolado.
- Ensaio live: `qwen/qwen3-14b` respondeu numa chamada observável sobre projeção
  `PARTIAL`, reconhecendo que a nota do workspace não estava validada.
- Um ensaio adversarial revelou confusão entre uma falsa autoridade declarada
  no corpo da nota e os metadados reais. A preparação passou a produzir um
  `TRUSTED_AUTHORITY_MANIFEST` separado, única fonte de classificação no prompt.
- Repetido o mesmo ataque, o modelo preservou corretamente
  `UNVALIDATED_WORKSPACE_PROPOSAL` / `UNVALIDATED_WORKSPACE` e recusou a
  autopromoção.
- Resultado: 204 testes Diamond; 391 testes totais; 8/8 v8 e 4/4 cross-v2
  permanecem verdes.

### Desenho WIP — memória Φ− e dupla fronteira

- Separada a admissibilidade positiva da exclusão justificada no mesmo âmbito.
- Φ− passa a designar memória auditável de propostas excluídas, não lixo nem
  negação de Φ.
- Definida uma matriz com quatro resultados: admissível, excluído, conflito e
  indeterminado.
- Proposto o reaproveitamento de cartões, conceitos e tópicos para compactar
  padrões de exclusão sem misturá-los com memória positiva.
- Regras derivadas seguem o ciclo `OBSERVED_FAILURE -> REPEATED_PATTERN ->
  SCOPED_RULE -> DERIVED_INVARIANT`.
- Frequência isolada não autoriza promoção e nenhuma regra altera
  automaticamente o kernel.
- O primeiro corte recomendado é um journal append-only de eventos, agregação
  determinística de padrões e feedback de reparação.
- Desenho completo em [`PHI-MINUS-MEMORY.md`](PHI-MINUS-MEMORY.md).

### Desenho WIP — cláusula anti-entropia executável

- Relida a cláusula do Volume I como definição constitucional de identidade,
  não apenas como texto jurídico.
- Um componente que viole as restrições constitutivas pode existir como código,
  mas não recebe autoridade nem é reconhecido como módulo Fresta admissível.
- A compatibilidade declarada pelo próprio módulo é apenas uma proposta; o
  kernel deriva admissão através de contratos, proveniência, capacidades,
  planeamento, efeitos e evidência.
- Adotado o princípio `compatibilidade não demonstrada -> autoridade não
  concedida`.
- A proteção atravessa admissão, planeamento, autorização, execução,
  cristalização e auditoria Φ−.
- Reconhecido o limite do isolamento atual: mediação in-process não protege
  contra Python hostil; módulos comunitários reais exigirão processo ou RPC.
- A cláusula produz exclusões; a memória Φ− preserva e aprende com elas. São
  mecanismos complementares, não duplicados.
- Desenho completo em
  [`ANTI-ENTROPY-KERNEL.md`](ANTI-ENTROPY-KERNEL.md).

### Implementação parcial — Cognitive Workspace e `/learn` interno

- O workspace é uma mesa de folhas e backlinks, não memória principal nem
  sandbox de código hostil.
- A LLM pode criar rascunhos, hipóteses, relações e propostas com papéis
  contextuais.
- Uma folha prova apenas que algo foi proposto; nunca confirma o próprio
  conteúdo.
- Para sair do workspace, um objeto específico passa por `/learn`, Gatekeeper,
  três ordens e ónus epistémico.
- A LLM pode solicitar a blueprint, mas não autorizar promoção.
- Modo idle continua limitado por objetivo, critério, permissões e budget.
- Folhas, revisões, backlinks, intake, avaliação LLM e cristalização isolada já
  estão implementados; falta comparar qualidade e integrar a fronteira Φ−.
- Desenho completo em
  [`COGNITIVE-WORKSPACE.md`](COGNITIVE-WORKSPACE.md).

## Estado atual

O esqueleto modular consegue admitir/rejeitar manifestos por política
anti-entropia, registar módulos, comandos e blueprints; derivar e validar uma
cadeia de operações; executá-la com providers substituíveis; e mediar efeitos
externos por uma fronteira auditável.

O desacoplamento do código está protegido automaticamente. Existem adapter LLM
local limitado, `/learn` isolado, memória autónoma experimental, conceitos
versionados e pesquisa externa mediada. Isto ainda não equivale a autonomia
funcional nem a memória de produção.

Continuam WIP a pipeline geral de `/learn`, políticas reais de diversidade e
saturação de fontes, projeção de atenção e interfaces.

## Próximo corte recomendado

Definir políticas explícitas de diversidade/saturação de fontes e escolher
entre o próximo corte de conflito/revalidação conceptual ou uma primeira
projeção reutilizável de atenção sobre conceitos e cristais.

## Regras de trabalho

- Cada migração começa por comportamento observável e termina com teste.
- Compatibilidade legacy é explícita e temporária.
- Ordem armazenada num cartão não é tratada como essência permanente.
- A LLM decide onde existe decisão semântica; a mecânica fica em código.
- A janela da LLM é memória de atenção, não memória total.
- Nenhum efeito externo ignora o `EffectBroker`.
- Nenhum resultado experimental vira regra ontológica sem justificação.

## 2026-08-06 — decomposição determinística de objetos grandes

- `SheetDecompositionService` divide conteúdo por budget sem alterar Unicode,
  espaços, quebras de linha ou ordem.
- Cada folha de conteúdo conserva fonte, ordinal e SHA-256; a operação só fecha
  depois de reconstruir o original através das referências exatas.
- Fan-out grande cria índices-mãe intermédios limitados, sempre ligados por
  revisão+hash. Evolução posterior de um filho não reescreve o snapshot antigo.
- A autoridade permanece `UNVALIDATED_WORKSPACE_DECOMPOSITION`: integridade não
  equivale a verdade nem promoção de memória.
- O limite atual mede conteúdo; projeções devem reservar overhead do prompt.
  Fronteiras semânticas por O3 e ligação automática ao scheduler continuam WIP.
- Verificação: **256 testes Diamond; 443 testes totais**.

Próximo corte recomendado: quando a atenção detetar um objeto obrigatório que
sozinho excede o budget, decompor, substituir esse ref pelos filhos exatos na
continuação e retomar sem repetir os itens já concluídos.

## 2026-08-06 — recuperação automática da atenção oversized

- `attention_turn` liga agora o sleep sem progresso à decomposição determinística
  e tenta novamente uma única vez sobre os filhos limitados.
- O modelo nunca vê um falso batch vazio: overflow sem qualquer item selecionado
  é bloqueado antes de `llm.generate`.
- As continuações seguintes retomam só refs pendentes. Um teste percorre todos
  os filhos, sem repetição, até `READY`.
- O modo manual permanece disponível com `auto_decompose=False`.
- Verificação: **257 testes Diamond; 444 testes totais**.

Próximo corte recomendado: criar a camada de comandos partilhada, ainda sem UI,
para estabilizar as entradas públicas de atenção e `/learn`.

## 2026-08-06 — serviço central de comandos headless

- Criados contratos imutáveis de spec, invocação e resultado, registry com
  aliases e `DiamondCommandService` sobre a aplicação persistente existente.
- Centralizados `/learn`, criação/turno/retoma/estado da atenção e help.
- `invoke()` serve integrações estruturadas; `execute_line()` é apenas parser de
  conveniência. Ambos chegam aos mesmos handlers.
- Adicionado codec JSON estável e teste de extensão por comando comunitário sem
  editar o serviço ou qualquer interface.
- Verificação: **263 testes Diamond; 450 testes totais**.

Próximo corte recomendado: runner headless configurável e, sobre ele, REPL fino.

## 2026-08-06 — runner configurável e smoke live

- Adicionados config/constructor reutilizáveis e `run_commands.py`, que executa
  exatamente uma linha e exige data root explícito.
- Um smoke com budget de resposta demasiado pequeno revelou que tentativa de
  chamada não equivale a resposta. Criado estado `INCOMPLETE`, remainders no
  payload e exit code `3`.
- Segundo smoke real com `qwen/qwen3-14b`, 512 tokens de resposta: uma chamada,
  execução `COMPLETED`, resposta presente e zero remainders.
- Verificação: **267 testes Diamond; 454 testes totais**.

Próximo corte recomendado: REPL persistente mínimo, só como renderer/dispatcher.

## 2026-08-06 — propostas autónomas de módulos abaixo do controller

- Implementado o percurso `MISSING_CAPABILITY -> inventário -> reutilização ou
  proposta O1/O2/O3`, sem scaffold nem código executável.
- Provider exato produz `NO_NEW_MODULE` determinístico e zero chamadas à LLM.
- A LLM não controla capability, schemas, camada, efeitos ou permissões. Estes
  últimos são subconjuntos de uma fronteira do host, vazia por defeito.
- O preflight anti-entropia rejeita escapes constitucionais e guarda tanto
  propostas como rejeições num arquivo imutável verificado por SHA-256.
- Centralizados `/module suggest`, `/module proposals` e `/module inspect` no
  serviço partilhado de comandos.
- O smoke live com Qwen fez uma chamada e respondeu `NO_NEW_MODULE`, mantendo
  efeitos/permissões vazios, sem criar ou ativar código.
- Verificação: **282 testes Diamond; 469 testes totais**.

Próximo corte recomendado: REPL persistente mínimo, sem lógica cognitiva própria.

## 2026-08-06 — REPL persistente fino

- Criados `DiamondRepl` e `run_repl.py` sobre uma única aplicação e serviço de
  comandos durante toda a sessão.
- O adapter só trata prompt, JSON, saída, EOF e erros; não contém lógica de
  `/learn`, atenção, módulos ou memória.
- Streams por pipe omitem o prompt e podem produzir um objeto JSON compacto por
  linha. Em terminal real permanece a apresentação legível.
- Comandos inválidos, falhas e `Ctrl+C` não destroem a sessão. Resultados
  `INCOMPLETE` permanecem incompletos.
- O smoke live chamou a Qwen uma vez; a resposta omitiu `determinism`, foi
  recusada honestamente, e o comando offline seguinte correu no mesmo processo.
- Verificação: **287 testes Diamond; 474 testes totais**.

Próximo corte recomendado: centralizar conceitos, pesquisa e workspace na mesma
superfície antes de construir o Web.

## 2026-08-06 — vínculo constitucional obrigatório por análise

- Criada uma fronteira de firewall obrigatória em cada execução do controller.
- Cada resultado conserva uma attestation imutável; ausência explícita impede a
  construção do controller.
- O journal regista a condição constitucional antes do plano e mantém a cadeia
  causal também em resume.
- A aplicação persistente reutiliza a mesma fronteira em todos os seus
  controllers.
- A documentação pública descreve apenas o contrato e as garantias observáveis;
  intake semântico e hardening continuam honestamente WIP.
- Verificação: **294 testes Diamond; 481 testes totais**.

## 2026-08-06 — primeiro intake semântico da firewall

- Sinais internos apenas ativam revisão; não escolhem automaticamente a
  decisão constitucional.
- Uma proposta contextual tipada é convertida pelo host em transformação
  segura, quarentena ou negação. Ausência/falha da revisão necessária fica em
  quarentena.
- Linguagem operacional confirmada é negada; a mesma linguagem citada para
  análise crítica pode passar como referência segura.
- Um falso positivo real sobre proveniência inventada estreitou o trigger sem
  fragilizar o validador de aprendizagem existente.
- Verificação: **299 testes Diamond; 486 testes totais**.

## 2026-08-06 — revisão semântica mediada e primeiro red team

- A revisão da firewall passou a ser uma operação tipada com efeito de modelo
  limitado e contabilizado juntamente com as chamadas da tarefa.
- O modelo apenas propõe a leitura contextual; campos de autoridade ou efeitos
  adicionais não atravessam o decoder.
- O primeiro corpus local encontrou falhas de cobertura e um falso positivo
  legítimo. Ambos foram corrigidos e preservados por regressões.
- Dois smokes sequenciais com Qwen distinguiram oito casos operacionais e
  benignos sem chamadas paralelas.
- Verificação: **308 testes Diamond; 495 testes totais**.

## 2026-08-06 — organização do diretório Diamond

- Eliminada a ambiguidade entre `testdata/` e `data-tests/`: o estado do smoke
  manual foi preservado em `testdata/local-runtime/`, fora das fixtures e
  baselines e ignorado pelo Git.
- `testdata/` continua a ser o único laboratório: fixtures, baselines, runs,
  comparação cruzada, catálogo conceptual e uma fronteira local não canónica.
- Movidos oito benchmarks/smokes especializados para `scripts/`; apenas
  `run_repl.py` e `run_commands.py` permanecem na raiz como interfaces públicas.
- Adicionado `.gitignore` autónomo para o futuro repositório independente e um
  README próprio dos scripts.
- Todos os entrypoints responderam a `--help`; 8/8 baselines Diamond e 4/4
  comparações cruzadas continuaram iguais; **287 testes Diamond e 474 totais**.

## 2026-08-06 — conceitos na superfície central de comandos

- Centralizados `/concept list`, `inspect`, `nominate` e `evaluate` sem criar
  pipelines próprias no REPL.
- A forma textual e `invoke("concept.*", ...)` partilham handlers e autoridade;
  a primeira destina-se ao utilizador e a segunda a integrações/blueprints.
- Nomination continua limitada a `CANDIDATE`; evaluation usa o validador
  determinístico existente e preserva a versão/história do conceito.
- Smoke offline do REPL: listagem `IDLE`, zero chamadas e help atualizado.
- Verificação: **289 testes Diamond; 476 testes totais**.

## 2026-08-06 — fronteira inerte para dados recuperados

- Documentos, cartões, conceitos, retrieval e atenção deixaram de entrar em
  regiões chamadas `trusted_*`; conteúdo natural passa apenas como dado sem
  autoridade de instrução.
- O `EffectBroker` valida todas as mensagens de `llm.generate`, mesmo fora da
  aplicação persistente, e bloqueia dados soltos antes do adapter.
- O envelope preserva exatamente o valor JSON mas neutraliza delimitadores que
  tentem criar tags ou papéis falsos.
- Um primeiro teste live mostrou lavagem semântica da instrução apesar do
  isolamento técnico. A segunda versão obrigou atribuição à fonte; o Qwen
  reconheceu a afirmação hostil e recusou a sua autoridade não corroborada.
- Verificação: **314 testes Diamond; 501 testes totais**.

## 2026-08-06 — fecho condicionado por atribuição à fonte

- O kernel confirmou a fronteira correta: não confundir coerência estrutural
  com verdade, mas também não permitir que “a fonte afirma X” seja reduzido a
  “X é aceite pelo sistema”.
- Intake constitucionalmente arriscado recebe um testemunho determinístico do
  host. O grafo só fecha se conservar atribuição explícita em O1 e uma limitação
  inequívoca de autoridade/validação em O2/O3.
- “Sem validação do kernel” deixou de contar como limitação, pois pode ser a
  própria descrição do bypass. Falta de autoridade, impossibilidade de
  autopromoção ou falta de corroboração são testemunhos admissíveis.
- No teste live, V1 e a única reparação repetiram a relação inválida; ambas
  permaneceram abertas com remainder. Não houve convergência fabricada.
- Corrigidos o JSON recursivo do runner e a aceitação de tuplos congelados pelo
  repair.
- Verificação: **319 testes Diamond; 506 testes totais**.

## 2026-08-06 — `/learn` contaminado e catálogo do kernel

- Criada fixture isolada com facto reportado, falsidade reportada, armadilha de
  identidade ficcional e injeção constitucional.
- O primeiro sweep foi seguro, mas revelou um wrapper redundante em
  `candidate_assessments`; o contrato foi clarificado e apenas essa equivalência
  conhecida é normalizada.
- A classificação epistémica passou a receber opções canónicas do kernel,
  respetivos significados, disponibilidade contextual e `DEFER`. A análise
  permanece aberta; só a etiqueta final deixa de ser adivinhada.
- Smoke live da falsidade: uma chamada, `ATTESTATION`, fecho estrutural e
  epistémico, cristal `PROVISIONAL`, sem observação nem verdade aceite.
- A injeção é preservada para auditoria mas termina em quarentena obrigatória.
- Dois grafos normais continuaram deferred por ligações estruturais mecânicas;
  o próximo catálogo deve cobrir escolhas finitas de ligação e repair.
- Verificação: **323 testes Diamond; 510 testes totais**.

## 2026-08-06 — provider de reflexão condicionado e persistência proposta

- Ligado `LlmReflectionOperation` a uma blueprint/manifest real do controller,
  mantendo `llm.generate` atrás do `EffectBroker` e da firewall constitucional.
- `propose_chat_reflection()` materializa apenas referências do transcript já
  persistido; sem trigger ou sem transcript não existe chamada ao modelo.
- A resposta é ancorada pelo host em `REFLECTION_PROPOSAL_ONLY` e convertida,
  quando válida, num claim de perfil ou trait de personalidade `PROPOSED`.
  Nenhum caminho público escreve `ACTIVE`.
- IDs de transcript, target, scope e autoridade são host-owned; conteúdo
  malformado, target inválido ou autopromoção continuam a falhar fechados.
- Smoke live sequencial com `qwen/qwen3-14b` via LM Studio respondeu uma proposta
  `USER_PROFILE` sobre `NEW_PREFERENCE`, com autoridade não validada e sem
  persistência ativa.
- Verificação: **357 testes aprovados**.

## 2026-09-03 — Gatekeeper de adoção controlada

- Adicionado `ProfileAdoptionGatekeeper` separado da escrita pública dos stores.
- Uma proposta só pode ser adotada com confirmação explícita `ADOPT`; confiança,
  frequência ou resposta da LLM não promovem nada por si só.
- A adoção cria uma nova versão `ACTIVE`, preservando a linhagem da proposta
  anterior. Readoção de um registo ativo é recusada.
- A aplicação expõe handlers distintos para perfil do utilizador e personalidade;
  continua impossível escrever `ACTIVE` pelo store público.
- Verificação: **359 testes aprovados**.

Próximo corte recomendado: inspeção/auditoria das propostas e adoções, antes de
iniciar o inventário determinístico de `/brain analyze`.

## 2026-09-03 — inspeção read-only de perfil e personality

- Stores passaram a expor inspeções por registo ou globais, verificando hash e
  lineage através da mesma leitura selada usada no runtime.
- O relatório mostra referências de versão, estados e versão mais recente sem
  criar escrita, promoção ou confirmação implícita.
- A aplicação expõe superfícies distintas para inspeção de claims e traits.
- Verificação: **360 testes aprovados**.

Próximo corte recomendado: integrar estes relatórios num comando de auditoria
headless, antes do inventário determinístico de `/brain analyze`.

## 2026-09-03 — auditoria de perfil na superfície headless

- Adicionados `/profile inspect` e `/personality inspect` ao command service
  partilhado, com filtros opcionais por ID.
- Os comandos são read-only, não chamam a LLM e devolvem apenas referências,
  lineage e estados já verificados pelos stores.
- Help, parser e codec mantêm a mesma superfície para REPL e integrações.
- Verificação: **361 testes aprovados**.

Próximo corte recomendado: desenhar o inventário determinístico de `/brain analyze`.

## 2026-09-03 — primeiro corte de `/brain analyze`

- Criado relatório imutável com inventário determinístico de módulos nativos,
  commits de aprendizagem, conceitos, chats e propostas de perfil/personality.
- Diagnóstico é bounded e explícito; não chama a LLM, não altera stores e não
  transforma coerência em verdade.
- O relatório conserva autoridade própria (`BRAIN_ANALYSIS_REPORT_ONLY`), hash
  verificável e remainders que mantêm PHI aberta.
- Adicionado `/brain analyze` ao command service partilhado.
- Teste de repetição confirma o mesmo hash sem mutação nem chamadas ao modelo.
- Verificação: **362 testes aprovados**.

Próximo corte recomendado: teste live controlado com um estado Diamond não vazio,
seguido de desenho separado para qualquer futuro `/brain apply`.

## 2026-09-03 — diagnóstico ontológico no `/brain analyze`

- O relatório aceita agora um grafo estrutural bounded e reutiliza o
  `OntologicalValidator` determinístico.
- O diagnóstico distingue presença de O2 forte e estabilidade/justificação de
  O3 através de FILTER; relações sem testemunho concreto permanecem abertas.
- A saída conserva os remainders do grafo, não trata o parecer da LLM como fecho
  e mantém `phi_open=true` sempre.
- Testes cobrem tanto uma relação O2 testemunhada como a ausência das três partes
  do testemunho O2, sem fabricar fecho O3/PHI.
- Verificação: **364 testes aprovados**.

Próximo corte recomendado: construir um caso integrado não vazio através do
command service e executar o relatório completo sem mutações.

## 2026-09-03 — teste integrado não vazio do `/brain analyze`

- O command service cria agora um caso de regressão com chat persistido e claim
  `PROPOSED` antes de executar o relatório.
- O inventário observa corretamente o estado não vazio, incluindo chat e proposta,
  sem chamar a LLM nem alterar qualquer store.
- O teste confirma que a superfície continua observacional e que `phi_open`
  permanece verdadeiro.
- Verificação: **365 testes aprovados**.

Próximo corte recomendado: iniciar o desenho do próximo WIP de intake/documentos
ou aprofundar a auditoria ontológica sobre grafos reais.

## 2026-09-03 — primeiro corte de intake documental

- Criado `DocumentSource` imutável e content-addressed para ficheiros UTF-8.
- O intake verifica caminho regular, conteúdo não vazio, limite de bytes e
  SHA-256 sobre os bytes originais; falhas são explícitas.
- A aplicação expõe `ingest_document()` sem transformar leitura em `/learn`,
  verdade, memória ou autoridade.
- O `source_ref` é `document:<sha256>` e fica pronto para provenance da futura
  decomposição/batching.
- Verificação: **368 testes aprovados**.

Próximo corte recomendado: materializar este source em folhas bounded e ligar
as folhas à seleção normal de `/learn`.

## 2026-09-03 — materialização documental lossless

- `DiamondApplication.materialize_document()` usa o source content-addressed para
  criar uma decomposição de folhas bounded no workspace.
- A decomposição conserva `source_ref`, SHA-256, ordem e conteúdo exacto; a
  reconstrução dos leaves reproduz os bytes UTF-8 originais.
- Folhas e índices permanecem `DRAFT`/não validados e não entram em memória sem
  seleção explícita pela pipeline normal de `/learn`.
- Colisões de identidade são recusadas pelo workspace/decomposer, evitando
  reescrita silenciosa do mesmo documento.
- Verificação: **369 testes aprovados**.

Próximo corte recomendado: criar uma seleção bounded destas folhas e encaminhá-la
para o intake normal de `/learn`, preservando checkpoints entre lotes.

## 2026-09-03 — primeiro lote documental na pipeline `/learn`

- `learn_document_leaves()` aceita apenas refs exactas da decomposição e processa
  um lote bounded por chamada através do mesmo `learn_text()`/controller.
- Cada folha conserva scope e provenance `document:<sha256>`; folhas pendentes são
  devolvidas explicitamente para futura continuação/checkpoint.
- Revisões stale e IDs inventados são recusados antes de chamar a LLM.
- O teste integrado aprende uma folha, preserva as restantes como pending e
  confirma a criação de apenas um commit normal de aprendizagem.
- Verificação: **370 testes aprovados**.

Próximo corte recomendado: persistir o cursor/checkpoint dos lotes e permitir
resume sem repetir folhas já committed.

## 2026-09-03 — checkpoints documentais e smoke live da pipeline

- Criado `DocumentLearningCheckpoint` com hash, decomposition ID, objetivo e
  refs processadas/pendentes; checkpoints repetidos não podem mudar de conteúdo.
- `resume_document_learning()` valida a decomposição e retoma apenas refs
  pendentes, sem repetir folhas já processadas.
- O primeiro smoke live foi corretamente negado por permissões incompletas,
  revelando o desvio entre a grant do teste e as permissões reais do adapter.
- Repetido com `adapter.required_permissions`: uma chamada sequencial à
  `qwen/qwen3-14b` concluiu `COMPLETED`, criou um commit e deixou zero remainders;
  os validadores reportaram fecho estrutural e epistémico para o caso bounded.
- Este fecho é local ao objeto/análise do caso e não fecha PHI constitucional.
- Verificação: **370 testes aprovados**.

Próximo corte recomendado: expor inspeção/resume dos checkpoints no command
service e testar uma interrupção entre lotes.

## 2026-09-03 — inspeção headless de checkpoints documentais

- Adicionados `/document checkpoints` e `/document checkpoint CHECKPOINT_ID`.
- A inspeção valida o hash do cursor e expõe decomposition, objetivo, folhas
  processadas e refs pendentes sem chamar a LLM ou alterar o workspace.
- O resume permanece tipado na aplicação até existir uma reconstrução persistente
  da decomposição que seja segura para a superfície textual.
- Verificação: **370 testes aprovados**.

Próximo corte recomendado: modelar essa reconstrução exacta para permitir
`/document resume` sem depender de objectos em memória.

## 2026-09-03 — reconstrução persistente e `/document resume`

- Checkpoints passaram a guardar a identidade completa da decomposição: source,
  hash, root, leaves, índices e budget bounded.
- A aplicação reconstrói refs exactas a partir do workspace, valida o hash por
  reconstrução lossless e só depois permite retomar.
- Adicionado `/document resume CHECKPOINT_ID [--max-leaves N]`, que continua
  apenas folhas pendentes através do controller normal.
- O comando é explicitamente model-capable, mas não concede autoridade nova:
  cada folha repete Gatekeeper, validação estrutural/epistémica e commit normal.
- Verificação: **370 testes aprovados**.

Próximo corte recomendado: teste de interrupção/resume pela superfície textual
com um documento multi-folha e adapter replay, seguido de smoke live bounded.

## 2026-09-03 — resume textual após interrupção entre lotes

- Checkpoints passaram a reconstruir a decomposição completa a partir do
  workspace persistido, verificando refs hash-bound e reconstrução lossless.
- `/document resume CHECKPOINT_ID [--max-leaves N]` retoma apenas folhas
  pendentes pela pipeline normal; a folha previamente committed não é repetida.
- O teste de interrupção usa o command service real e confirma dois commits
  distintos, cursor pendente e chamadas apenas para o lote retomado.
- Um erro de validação do argumento `--max-leaves` foi corrigido e coberto.
- Verificação: **371 testes aprovados**.

Próximo corte recomendado: smoke live multi-folha com interrupção deliberada,
sem ultrapassar os budgets e grants declarados.

## 2026-09-03 — sincronização do estado público com os WIPs reais

- `docs/STATUS.md` deixou de descrever stores, reflexão, `brain analyze` e
  aprendizagem documental como não implementados.
- As limitações permanecem explícitas: convergência documental completa,
  hardening, retenção, isolamento forte, Web e Workspace Agent continuam WIP.
- O README distingue agora implementação bounded de maturidade de produção, sem
  transformar testes locais em alegação de completude.
- Publicado `docs/CONNECTION-MAP.md`, ligando command service, aplicação,
  blueprints, controller, firewall, `EffectBroker`, Gatekeepers, stores e
  remainders. O mapa reafirma que completude operacional não é fecho
  epistémico nem fecho de PHI.
- Criado adapter HTTP mínimo em `web_adapter.py`: apenas loopback, `GET
  /health`, `POST /command`, limite de body e reutilização exclusiva do
  `DiamondCommandService`. A política de autenticação/deployment fica aberta
  antes de qualquer exposição além do processo local.
- A meta-análise foi ancorada no kernel: análises podem ser O1 compostos,
  convergência explícita reforça O2, e F exige evidência ligada a O3. Um
  candidato coerente só é reconhecido com caminho válido `O3 -> FILTER -> PHI`;
  isto ancora Φ como condição de possibilidade sem o fechar.
- Criado `identity.py` com separação entre `COHERENT_CANDIDATE` e
  `ACTIVE_SOCIAL_IDENTITY`. Coerência convergente não concede autoridade social;
  activação exige evidência de autoridade/consentimento com scope explícito.
- O Web adapter recebeu um token efémero por processo. O token autoriza apenas
  o transporte local (`POST /command`), não é identidade social, não é
  evidência ontológica, não é persistido e nunca é enviado à LLM.
- O retrieval de atenção passou a resolver também versões `ACTIVE` de perfil do
  utilizador e personalidade do assistente, através do mesmo
  `CompositeAttentionResolver`, mas em stores e namespaces distintos.
  Propostas continuam inelegíveis e a memória de tarefas não apaga esses
  domínios duráveis.
- A memória meta/ontológica passou a ter store versionado próprio e entrada no
  retrieval comum. A regra explicitada é que não há diferenciação sem Φ como
  abertura e F como filtragem; transparência exige expor O1, O2, O3, FILTER,
  Φ+, Φ-, remainders e o caminho de grounding, tanto no sistema como na
  análise.

## 2026-09-03 — smoke live multi-folha com reinício e resume

- O documento foi dividido em 48 folhas bounded; a primeira foi processada numa
  chamada live ao `qwen/qwen3-14b`.
- A aplicação foi reiniciada sobre o mesmo data root e reconstruiu a decomposição
  pelo checkpoint hash-bound.
- `/document resume` processou a folha seguinte, fez as chamadas necessárias
  (incluindo repair bounded) e criou o segundo commit.
- A primeira folha não foi repetida: 47 refs ficaram pendentes antes do resume,
  46 depois; a reconstrução root permaneceu exacta.
- A interrupção/resume é operacional; não equivale a verdade global nem fecha
  PHI, e a análise permanece relativa ao objectivo bounded.

## 2026-09-03 — hardening da convergência meta-ontológica

- A convergência deixou de aceitar apenas repetição de conteúdo: uma proposta
  coerente exige diversidade explícita de proveniência entre pelo menos duas
  análises.
- IDs de análise duplicados são rejeitados como remainder, evitando contar a
  mesma fonte duas vezes.
- Sem diversidade suficiente, o resultado permanece `INCOMPLETE`; não há
  promoção para `COHERENT_CANDIDATE` nem fecho de Φ.
- O hardening do Web revelou e corrigiu uma falha de ligação: a validação
  comparava contra um literal em vez do token efémero gerado. O adapter exige
  agora `Bearer <token>` real e usa comparação constante.
- Verificação: **389 testes totais aprovados**.

## 2026-09-03 — interface Web local utilizável

- Criado `run_web.py`, que inicia uma aplicação persistente com os mesmos
  parâmetros do runner/REPL e imprime URL e token efémero.
- O adapter serve uma UI local mínima em `/`, com campo de token, execução de
  comandos e visualização JSON dos resultados.
- A UI não cria uma cadeia cognitiva paralela: usa exclusivamente
  `DiamondCommandService`, mantendo os mesmos stores, budgets e authorities.
- Smoke real do launcher respondeu `200` em `/health`; a suite completa passou
  com **390 testes**.

## 2026-09-03 — O2 meta exige análises distintas

- Uma `ConvergenceEvidence` com duas referências iguais (`a1`, `a1`) já não
  pode satisfazer a relação O2 entre análises.
- O caso permanece `INCOMPLETE` com remainder explícito; repetição não é
  convergência e não altera a abertura de Φ.
- Verificação: **391 testes totais aprovados**.

## 2026-09-03 — estados epistémicos para lacunas de convergência

- `MetaAnalysisReport` separa agora o estado estrutural do estado epistémico:
  `INTERNAL_ONLY`, `EXTERNAL_ONLY`, `MIXED_PROVENANCE`,
  `INSUFFICIENT_GROUNDING` e `CONTESTED`.
- Remainders recebem códigos explicativos: O2 ausente/inválido,
  grounding `O3 -> FILTER -> PHI` em falta, independência de fonte não
  estabelecida, identidade duplicada ou conflito por resolver.
- A classificação é diagnóstico transparente da proveniência e da lacuna; não
  transforma informação externa em verdade, não cria autoridade e não fecha Φ.
- A proveniência desconhecida permanece `UNCLASSIFIED`, evitando inferências
  sobre se veio da rede ou de dentro do Fresta.
- Verificação: **391 testes totais aprovados**.

## 2026-08-06 — montagem estrutural canónica

- Aplicado às ligações estruturais o mesmo princípio usado na classificação
  epistémica: a LLM escolhe uma forma finita reconhecida pelo kernel, mantendo
  liberdade total no conteúdo dos testemunhos.
- `SINGLE_WITNESS_CHAIN` é compilado pelo host para IDs e ligações O1/O2/O3,
  FILTER e custo; `DEFER_STRUCTURE` conserva a abertura explicitamente.
- Adicionado um catálogo separado para a relação da fonte com a autoridade do
  kernel. Autopromoção/bypass pode ser nomeado sem adquirir autoridade.
- Smoke de controlo convergiu numa chamada sem repair. Smoke adversarial
  selecionou `UNTRUSTED_SELF_AUTHORITY_CLAIM`, fechou a compreensão estrutural
  numa chamada e continuou em quarentena — fecho não equivale a promoção.
- Verificação: **327 testes Diamond; 514 testes totais**.

## 2026-08-06 — catálogo relativo de repair

- Cada remainder de aprendizagem recebe ações permitidas relativas ao erro;
  não existe uma cadeia universal escrita à mão para todos os repairs.
- A resposta escolhe uma ação por target e fornece rationale. Escolhas, faltas,
  duplicações e IDs inválidos ficam arquivados; só os validators fecham o caso.
- `DEFER_REPAIR` conserva abertura e a escolha de fonte não confiável liga-se
  à montagem canónica de autoridade sem conceder promoção.
- Criado `scripts/run_repair_qwen.py` para um smoke isolado e deliberadamente
  defeituoso. Qwen corrigiu OBSERVATION para ATTESTATION numa chamada, sem
  remainder final nem erro no plano de repair.
- Verificação: **328 testes Diamond; 515 testes totais**.

## 2026-08-07 — repair partilhado e conceitos canónicos

- Extraída a política de ações para `repair_policy.py`; `/learn` e análise geral
  deixaram de manter derivações paralelas do mesmo catálogo.
- O repair geral arquiva ações/erros e inclui `repair_actions` no próprio schema
  pedido ao provider. O primeiro live corrigiu ontologia mas omitiu a ação;
  depois da clarificação do schema, o segundo selecionou uma ação válida e
  fechou a análise constitucional numa chamada.
- A evidência conceptual passou a usar a montagem estrutural canónica. IDs e
  ligações são host-owned; conteúdo O1/O2/O3 continua model-owned.
- No live conceptual, estrutura e epistemologia fecharam, mas faltou um selo
  positivo para uma exclusão. O conceito permaneceu CANDIDATE: lacuna semântica
  preservada para evidência/pesquisa, não mascarada como repair mecânico.
- Verificação: **330 testes Diamond; 517 testes totais**.

## 2026-08-07 — resolução dirigida de lacunas conceptuais

- A pesquisa conceptual pode agora receber referências exatas às partes em
  falta. Uma exclusão sem selo positivo gera apenas a pesquisa de fronteiras,
  sem transformar o nome do conceito numa pesquisa geral escondida.
- `DiamondApplication.resolve_concept_gaps()` encadeia mecanismos já existentes:
  pesquisa mediada, artefacto de fonte, `/learn`, revisão imutável do candidato
  e nova avaliação. A internet não valida nem promove diretamente.
- Só cristais que o `/learn` colocou em memória ACTIVE entram na nova versão do
  conceito. Resultados vazios ou aprendizagem deferred terminam sem mutação.
- O teste determinístico ponta-a-ponta parte de um conceito com uma exclusão
  não fundamentada, aprende uma fonte simulada e valida a revisão seguinte.
- Smoke live com `--resolve-gaps`: o Qwen resolveu o conceito logo na primeira
  avaliação; 1 chamada, versão 2 `VALIDATED`, zero remainders e nenhuma pesquisa
  desnecessária.
- Verificação: **332 testes Diamond; 519 testes totais**.

## 2026-08-07 — resolução conceptual no serviço central

- Criado `evaluate_and_resolve_concept()` na aplicação: a segunda etapa nasce
  do remainder pesquisável da avaliação, não de chaining no REPL/Web.
- Novo `/concept resolve`, também acessível por `invoke("concept.resolve")`,
  com budgets explícitos de queries e resultados.
- Fecho na avaliação inicial não chama a internet. Lacuna suportada reutiliza
  pesquisa → `/learn` → revisão → reavaliação; candidato ainda aberto retorna
  `INCOMPLETE`.
- O payload conserva metadados de auditoria e versões, sem despejar conteúdo da
  fonte. O smoke `/help` do REPL mostrou o comando sem chamadas à LLM e sem
  alterações cognitivas no adapter.
- Verificação: **332 testes Diamond; 519 testes totais**.

## 2026-08-07 — retrieval e folha ativa na superfície central

- `/attention retrieve` reutiliza a nomeação relativa ao objetivo,
  materialização exata, batching e continuação existentes. O payload conserva
  autoridade, papéis contextuais e custo sem copiar o conteúdo recuperado.
- Fachadas novas da aplicação criam, leem e acrescentam à folha ativa;
  `/workspace create`, `show` e `append` apenas traduzem argumentos.
- Testes provam seleção O2 de uma folha exata e projeção injection-ready, além
  da passagem imutável da revisão 1 para a revisão 2 sem chamar a LLM.
- O REPL herdou os comandos automaticamente através do serviço partilhado.
- Verificação: **334 testes Diamond; 521 testes totais**.

## 2026-08-07 — primeiro percurso persistente de chat

- Criado store dedicado `chat/`: binding selado e mensagens encadeadas por hash,
  com papéis/autoridades fixos e rejeição de adulteração ou IDs repetidos.
- A sessão liga atenção e folha-transcrito; o chat store é histórico canónico e
  a folha é apenas projeção DRAFT. Conversa não promove memória ou perfil.
- Inventário vazio inicia chat limpo deterministicamente, sem chamada inútil.
- `/chat start`, `say`, `status` e `list` chegam à aplicação pelo serviço comum.
- Testes cobrem store, reload, ataques ao histórico, retrieval, atenção,
  transcrito, comandos e ausência de commits implícitos.
- Limites registados em `CHAT.md`, incluindo sync após sleep e falta de perfis.
- Verificação: **340 testes Diamond; 527 testes totais**.

## 2026-09-03 — typed provenance contracts and lineage

- Kernel contracts now classify provenance conservatively as INTERNAL, EXTERNAL, MIXED, or UNKNOWN; legacy lists remain decodable without trusting caller-supplied labels.
- Concept research queries carry typed pre-search intent, and source units preserve source-document/extracted-unit lineage. Objective retrieval carries the same provenance without breaking legacy APIs.
- Phi remains open. No scholarly network adapter was added; existing bounded external research remains broker-mediated.
- Verification: **403 tests passed**.

## 2026-09-03 — explicit source lineages and bounded diagnostics

- Source independence is now an explicit `source_lineage` carried by typed
  provenance, source documents, extracted units, external source units and
  structural manifestations. Different URLs remain locator diagnostics only;
  they cannot establish independent support.
- Meta-analysis reports conservative saturation and revalidation diagnostics.
  These diagnostics do not close Φ, grant authority, or replace O1/O2/O3,
  FILTER, or Gatekeeper decisions.
- Verification: **403 tests passed**.

## 2026-09-03 — smoke Web com GPT OSS e transporte corrigido

- O processo Web imprimia o token já com `Bearer`, enquanto a UI acrescenta esse
  esquema no cabeçalho; a saída foi corrigida para expor apenas o token bruto.
- Propostas de query do GPT OSS podem representar `query_id` como inteiro; a
  fronteira normaliza esse identificador sem relaxar os restantes contratos.
- Uma investigação sem unidades de fonte agora termina como `INCOMPLETE` e não
  cria uma resposta de atenção sem evidência externa.
- Smoke live: autenticação e percurso Web responderam; com `openai/gpt-oss-20b`,
  o estado seguro foi `INCOMPLETE` quando a pesquisa não produziu fontes,
  mantendo Φ aberto. **427 testes passaram.**

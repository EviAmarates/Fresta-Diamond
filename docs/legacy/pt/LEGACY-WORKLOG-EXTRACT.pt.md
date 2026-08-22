# Diamond — arquivo histórico migrado

Estas notas foram movidas mecanicamente de `CODEX-WORKLOG.md` em 2026-07-25. O conteúdo histórico abaixo foi preservado; para o estado canónico atual, consultar `INDEX.md` e `WORKLOG.md`.

## Lab-to-diamond boundary

Tiago's intended split is not an in-place replacement:

- The current Fresta is the **Frankenstein/lab**. It remains available for rapid
  experiments, live LLM probes, feature flags, alternate implementations, and
  discovery of failure modes.
- The future clean Fresta is the **diamond**. It receives only behavior whose
  purpose and contract are understood and tested. It does not copy production
  data, unused functions, experimental profiles, duplicate commands, old
  prompts, or legacy paths unless a fallback is demonstrably necessary.
- Functional equivalence means preserving desired capabilities and justified
  outcomes, not reproducing current implementation details or known bugs.
- The first clean version is headless. No web, REPL, or user command surface is
  needed; direct Python contracts, deterministic tests, fixtures, and a small
  developer runner are sufficient until the core is functional.

Recommended next sequence:

1. Do not broadly clean the Frankenstein and do not yet copy its current
   pipeline wholesale.
2. Finish enough of the kernel v3 draft to specify Three-Order roles, recursive
   filtering, and structural-versus-epistemic state.
3. Implement only those missing contracts in the Frankenstein, where existing
   profiles and live Qwen tests can expose mistakes cheaply.
4. Resolve the V11 contract-level contradictions that affect the clean core:
   collective structural validation versus per-card state, active versus
   historical remainders, and the lifecycle of pending staged cards.
5. As soon as those contracts pass deterministic and one bounded live test,
   create the clean headless project and migrate the first vertical nucleus:
   kernel + claim/card schema + lifecycle + auditable analysis workspace.
6. Leave topics, source research, commands, REPL, and web in the lab until the
   nucleus is independently functional; promote each later only after its own
   contract stabilizes.

This prevents both failure modes: copying immature complexity into the diamond,
or spending indefinitely polishing laboratory code that will not be shipped.

## Diamond modular architecture contract

- Created `diamond/docs/ARCHITECTURE.md` as the pre-code contract for the
  clean prototype. It is explicitly subordinate to the ontological kernel and
  contains no UI, production-data, or provider-specific assumptions.
- Architectural mapping: kernel = invariant validator; registry = module and
  operation catalog; resolver = capability/artifact DAG derivation; plan
  validator = dataflow/Three-Order/effect closure; effect broker = scoped
  authorization; runtime = execution/checkpoint/budget; controller = small
  dependency-injected façade; workspace = provisional process memory.
- A module and operation remain order-neutral. Relative to a bounded blueprint
  outcome, registry/semantic matching is weak-O2 nomination; a validated plan
  records contextual O1 manifestations, explicit O2 dependencies/witnesses,
  and O3 constraints/effects/completion boundaries.
- Blueprints may name versioned capabilities and artifact outcomes but not
  providers or fixed operation chains. Modules never call one another; they
  return typed artifacts or bounded subobjectives/PHI to the controller.
- Community modules declare manifests, version compatibility, operations,
  schemas, effects, permissions, cost, determinism, idempotency, and failure
  modes. Discovery is not enablement. Handlers receive immutable artifacts and
  short-lived granted ports, never shared mutable state or direct memory access.
- LLM use is intentionally downstream of exact compatibility filtering. It may
  interpret objectives, rank technically valid alternatives, fill typed inputs,
  or propose mappings/blueprints; it cannot register modules, fabricate
  capabilities, authorize effects, or override closure.
- Added first-prototype substitution proof: provider A and provider B must
  satisfy the same blueprint without controller edits; incompatible,
  unauthorized, and missing providers must produce deterministic rejection or
  explicit PHI rather than magic fallback.
- Added serializable `PhiRemainder`, `ClosureReport`, and execution-state
  contracts so technical completion, constitutional closure, structural
  closure, operational convergence, epistemic closure, and historical
  resolution cannot collapse back into one boolean.
- Decisions deliberately deferred: entry points vs module directory,
  in-process vs subprocess/RPC isolation, concrete schema language, event
  storage, signature infrastructure, optimizer, and concurrent scheduler.

## Diamond milestone 1 — substituição de providers

- O primeiro corte executável vive agora isolado em
  `diamond/src/fresta_diamond/`; não importa
  módulos do Frankenstein, não lê `data/`, não chama a LLM e não contém UI.
- Foram implementados contratos imutáveis para artefactos, manifests,
  operações, blueprints, planos, PHI, fecho e resultados de execução.
- O registry segue `discover -> verify -> enable`: código executável só é
  associado depois da verificação explícita do manifest.
- O resolver seleciona providers por capability, schemas, efeitos e permissões;
  incompatibilidade, ausência ou falta de autorização tornam-se PHI explícito,
  sem fallback mágico.
- O runtime executa apenas um plano previamente validado e passa ao handler um
  contexto limitado, sem acesso à memória global.
- Foi acrescentado um `DiamondController` fino e injetado. O mesmo controlador,
  a mesma blueprint e o mesmo input executaram primeiro com o provider A e,
  depois de o desativar, com o provider B sem alterações no consumidor.
- Limite deliberado deste marco: uma capability exata e um único nó. DAGs,
  validador separado, effect broker e blueprints compostas pertencem aos
  próximos cortes, não estão implicitamente fingidos nesta implementação.
- Verificação: suite Diamond **6 passed**; suite completa **187 passed**.
  Production `data/` e Git não foram tocados.

## Diamond milestone 2 — DAG derivado e validação separada

- `BlueprintSpec` aceita agora várias requirements tipadas. A ordem em que são
  declaradas não prescreve a cadeia: o resolver deriva a ordem pelos artefactos
  disponíveis e pelos schemas de entrada/saída.
- As requirements atribuem papéis O1/O2/O3 apenas relativamente ao objetivo da
  blueprint. Os módulos e operações continuam ontologicamente neutros.
- O resolver produz exclusivamente planos `PROPOSED`. Um `PlanValidator`
  separado é a única peça que pode elevar o plano a `VALIDATED`; o runtime
  recusa executar propostas ou planos rejeitados.
- O plano contém bindings de outputs e arestas tipadas explícitas. O validador
  recompõe as dependências a partir dos bindings e rejeita diferenças entre o
  grafo declarado e o grafo efetivo como `CONTRADICTION`.
- O validador confirma disponibilidade/versão das operações, schemas,
  dataflow, outcomes requeridos, efeitos/permissões e suporte contextual das
  três ordens. Lacunas permanecem como PHI tipado.
- Prova executável: requirements declaradas como síntese, normalização e
  relação foram derivadas e executadas na ordem
  `normalizer -> relater -> synthesizer`, com dois artefactos intermédios.
- Foram testados plano adulterado, autoridade exclusiva do validador e ciclo de
  dependências sem input externo; nenhum deles é executado por fallback.
- Limites deliberados: operações unárias, execução topológica sequencial,
  autorização ainda incorporada na validação e sem effect broker/checkpoints.
- Verificação: suite Diamond **10 passed**; suite completa **191 passed**;
  cinco módulos Diamond compilados. Production `data/` e Git não foram tocados.

## Diamond milestone 3 — EffectBroker e auditoria ontológica

- Foi implementada a transição separada
  `PROPOSED -> VALIDATED -> AUTHORIZED -> RUNNING`. O runtime exige uma
  autorização ligada ao `plan_id` e um grant correspondente a cada nó.
- Manifest declaration, blueprint allowance, adapter availability e invocation
  são condições distintas. Um efeito permitido mas sem adapter instalado é
  recusado antes de executar o handler.
- `ExecutionContext.invoke()` só expõe adapters incluídos no grant imutável do
  nó. O adapter recebe o grant completo para aplicar restrições de recurso.
- Uma tentativa do handler de invocar um efeito fora do grant produz
  `PERMISSION_DENIED`; exceções comuns continuam `FAILED`, não são confundidas
  com autorização.
- Limite de segurança explícito: isto é mediação da API in-process, não sandbox
  contra Python hostil. Isolamento forte aguarda subprocess/RPC.
- A auditoria contra `ONTOLOGICAL_KERNEL-v3-DRAFT.md` encontrou e corrigiu uma
  sobredeclaração: terminar um DAG técnico não prova strong-O2, FILTER nem a
  rota O3->FILTER->PHI. Por isso, execução bem-sucedida passa a reportar
  `structural_closed=None` e `constitutional_closed=None` até existir um
  validador ontológico determinístico.
- Contextual roles numa requirement são agora opcionais e permanecem
  nominations relativas ao objetivo; a simples presença de O1/O2/O3 já não é
  tratada como fecho.
- Foi identificada dívida terminológica: `PhiRemainder`/`phi` transporta também
  lacunas finitas. Antes de estabilizar serialização, migrar para
  `Remainder`/`RemainderKind` e reservar PHI para incompletude constitucional.
- Criado `diamond/docs/STATUS.md` como mapa curto e autoritativo de retoma do
  protótipo: fluxo, marcos, fronteira ontológica, limitações, roadmap e checklist.
- Verificação: suite Diamond **15 passed**; suite completa **196 passed**;
  módulos Diamond compilados. Production `data/` e Git não foram tocados.

## Immediate resume point — Diamond

1. Começar por `diamond/README.md` e `diamond/docs/STATUS.md`; não reconstruir
   o plano a partir do chat.
2. Próximo corte recomendado: corrigir a nomenclatura genérica de remainders e
   introduzir o contrato de evidência estrutural/validador ontológico separado.
3. Só depois implementar workspace/event journal, budget/checkpoint/sleep e DAG
   geral; a LLM local entra posteriormente como provider substituível.
4. O Frankenstein permanece a bancada funcional; o Diamond permanece isolado,
   sem UI nem produção, até uma fatia de `/learn` passar comparação A/B.

## Diamond documentation organization

- Criada a pasta-hub `diamond/` para reduzir a dispersão do protótipo.
- `diamond/README.md` explica em português o objetivo do Fresta Protocol, a
  relação entre kernel, Frankenstein e Diamond, o fluxo arquitetural, estado
  implementado, WIP, mapa de ficheiros e regras de desenvolvimento.
- Os documentos exclusivos foram organizados em
  `diamond/docs/ARCHITECTURE.md` e `diamond/docs/STATUS.md`.
- Numa segunda reorganização, os redirecionamentos raiz foram removidos e todo
  o material exclusivo passou fisicamente para `diamond/`.
- O código foi movido para `diamond/src/fresta_diamond/` e os testes para
  `diamond/tests/`, sem cópias divergentes. O package limpo chama-se
  `fresta_diamond`, separado do Frankenstein `fresta`.
- `diamond/pyproject.toml` permite testar/empacotar o protótipo isoladamente; o
  `pyproject.toml` raiz inclui os source/tests do Diamante apenas na verificação
  geral, sem misturar o seu package com a distribuição Frankenstein.
- O índice do `README.md` principal aponta agora para o portal do Diamante.
- As antigas pastas vazias do package Frankenstein e da suite raiz foram
  removidas após a migração.
  Todo o material exclusivo (código, testes, configuração e docs) está sob
  `diamond/`; fora dela restam apenas integração/índice/configuração global.
- Verificação pós-organização: links locais válidos; suite Diamond pela raiz
  **15 passed**; suite Diamond isolada dentro do subprojeto **15 passed**; suite
  completa **196 passed**. Production `data/` e Git não foram tocados.

## EDGE recovery — lenses for concepts and attention

- Original repository: `https://github.com/EviAmarates/fresta-edge`.
- EDGE is not part of the ontological kernel. Its best future role is a
  goal-scoped lens generator between concepts, attention memory, the LLM, and
  user-facing communication.
- Distinction to preserve:
  - a concept states a relatively persistent semantic identity, features,
    boundaries, relations, examples, and counterexamples;
  - a lens is a temporary projection of that concept for one objective, user,
    scale, horizon, and state.
- Fixed O1/O2/O3 roles are legitimate inside the original EDGE because its
  blueprint fixes one domain and evaluation scale: local metrics, their
  dependencies, and systemic constraints. They are scoped structural roles,
  not universal properties. When a lens component becomes an object in another
  Diamond analysis, it receives a separate dynamic contextual role.
- Proposed attention flow:
  `objective -> activate concepts -> propose/reuse EDGE lenses -> retrieve by
  lens characteristics -> contextual analysis -> update attention -> output`.
- Lenses may support chat, `/learn`, research, decisions, sandbox work, and
  maintenance. A useful cache key is
  `(concept_id, objective_class, scope_version)`; lenses expire or are revised
  with the task rather than entering long-term memory automatically.
- Important safeguard: generate a counter-lens for costly decisions so the
  active filter records what it excludes. Repeatedly useful lens structure may
  be proposed through the ordinary gatekeeper, never persisted directly.
- Candidate Diamond capabilities:
  `lens.propose`, `lens.apply`, `lens.counter`, `lens.revise`, and
  `lens.summarize`. Internet and LLM calls remain replaceable authorized
  providers; lens outputs remain proposals with sources and provenance.
- Do not copy the legacy script unchanged. Preserve its scoped three-layer
  insight while correcting ambiguous ordinal fields, arbitrary global
  thresholds, unsourced/fallback inventions, schema inconsistency, and the old
  use of PHI+ for buyer profiles.

## Fresta Finance recovery — relational depth is not a new order

- Original repository: `https://github.com/EviAmarates/fresta-finance`.
- The historical names “4th order” (`E_tree`) and “5th order”
  (`E_political`) do not introduce ontological O4/O5. They expand O2 through
  additional relation kinds and graph distance: suppliers, customers,
  geographic roots, policy, regulation, and geopolitical exposure.
- Canonical distinction for Diamond:
  - `order` = ontological function (O1 manifestation, O2 relation/witness,
    O3 contextual constraint);
  - `relation_depth` = number or structural distance of dependency hops;
  - `relation_kind` = financial, sector, supply-chain, geographic, political,
    regulatory, or another typed relation.
- A relation graph may be arbitrarily deep without creating a fourth order.
  O2 may contain direct and multi-hop dependencies; O3 states the bounded
  resilience/admissibility criterion, stress scenario, horizon, and evidence
  limits under which those relations matter.
- Useful mechanisms to recover for Diamond:
  - deterministic local metrics plus stochastic structural proposals;
  - adaptive analysis depth/token budget based on object complexity;
  - per-object cache, checkpoint, interruption, and exact resume;
  - explicit dependency graphs, concentration, cycles, root diversity, and
    single points of failure;
  - staged baselines followed by object-specific adjustment;
  - intermediate artifacts forming a natural capability DAG.
- Fresta Finance is a strong future integration workload/community module, not
  kernel code. Candidate capabilities include market/source retrieval, local
  metric calculation, dependency graph construction, entropy/stress
  propagation, supply-chain proposal, political-risk proposal, lens
  composition, and report rendering.
- Corrections required before reuse:
  - schema/range validation does not prove factual truth;
  - failed LLM calls/default values must remain explicit remainders and must
    never be cached as `validated=true`;
  - missing financial data cannot silently become a neutral score;
  - price correlation and sector proximity nominate possible dependencies but
    do not prove causation;
  - current political/supply-chain claims need dated sources and provenance;
  - the weighted unified formula remains additive and cannot by itself prove
    the stated structural non-additivity;
  - add deterministic/adversarial tests before treating rankings as evidence.
- Potential Diamond normalization of a relation:
  `relation_kind`, `relation_depth`, `source_units`, `confidence`, temporal
  scope, `forward_effect`, `return_witness`, and `excluded_alternative/cost`.

## Objecthood, naming, and derived reference distinction

- Ontological object must not be confused with “object currently selected for
  analysis.” If something exists as a determinate object, it has already been
  filtered by F; if it has been filtered, its manifestation, relations, and
  admissibility constraint are in principle analyzable through the Three
  Orders.
- Naming is itself filtration. A name, concept, claim, or representation exists
  as a determined object once selected, while the unfiltered is not a hidden
  inventory of ready-made objects. Treating it as such would already filter it.
- PHI is the undetermined opening/irreducible exteriority that makes F possible,
  not a collection of absent entities. Naming PHI creates a finite filtered
  representation that points to but cannot exhaust transcendental PHI; recursive
  analysis therefore returns to incompleteness as fixed point.
- Crucial correction: the kernel does not need a hard-coded prior distinction
  between concept and referent, fictional and real, linguistic and empirical.
  Nor does it need an additional heuristic called epistemic caution. Tiago's
  “fear” of collapsing distinct determinations is PHI itself operating as
  transcendental condition: the constitutional refusal/inability of a filtered
  system to declare its representation complete. The Three-Order method derives
  the appropriate distinction for the current object and scope because PHI
  prevents any manifestation from being silently treated as total.
- Example: “unicorn” is first accepted simply as an existing filtered object.
  Depending on the objective, the analysis may support it as a cultural,
  narrative, symbolic, or economic object while leaving biological
  instantiation unsupported. That result comes from O1 manifestations, O2
  relations/witnesses, and O3 admissibility constraints; it is not preloaded as
  a fiction label.
- Operational consequence of PHI: never infer that two manifestations
  instantiate the same object, identity, or referent until a sufficiently
  grounded O2 under the relevant O3 supports the relation. Familiar wording,
  first person, similarity, or documentary proximity only nominate the
  relation. This is not an external safety rule placed after the method; it is
  the computational expression of constitutional incompleteness within it.
- This directly addresses the document/user contamination bug. Fresta should
  not need a permanent list of fictional characters or narrator types; it must
  refuse to identify a document's “I”, a Roman description, or a character with
  the actual user unless the contextual relation closes.
- Compact hierarchy derived in discussion:
  `PHI = condition of possibility and prohibition of total self-completion`,
  `F = differentiation/filtration`, and `O1/O2/O3 = method for making the
  structure of a filtered object explicit and auditable`. The method produces
  distinctions; it does not replace them with predeclared categories. What was
  informally called “fear” is the system's operational recognition that every
  determination is filtered and therefore cannot exhaust PHI.

## Every Three-Order analysis is meta-relative to its object

- A Three-Order analysis does not merely enumerate an object's internal
  content. Relative to bounded object `x`, it asks how `x` manifests (O1),
  which relations/dependencies make that manifestation possible or evidential
  (O2), and under which contextual filter/admissibility constraint it persists
  (O3). It therefore analyzes the structure of `x`'s determination and is
  always meta relative to `x`.
- “Meta relative to x” is not automatically reflexive `F(F)`. Ordinary
  Three-Order analysis moves from the object to its conditions. `F(F)` is the
  stronger transition in which the filtering operation/criterion previously
  used becomes the next explicit object and its representation can update the
  system that used it.
- The result of an analysis may become O1 in a subsequent analysis without
  creating O4 or proving metacognition. Recursion reassigns the same three
  contextual roles:
  `x -> meta(x) -> result R(x) -> R(x) as new object -> meta(R(x))`.
- Computational consequence for Diamond: every structural-analysis artifact
  should record at least `object_ref`, bounded objective/scope, parent analysis
  where applicable, contextual role assignments, and whether the filter itself
  became the analyzed object. This prevents ordinary recursive decomposition
  from being mislabeled as `F(F)` or `F(F(F))`.
- This unifies existing applications: `/learn` is meta-analysis of documents
  and generated cards; concepts are meta-structures over manifestations; EDGE
  lenses are goal-scoped meta-structures over domains; the controller derives
  a meta-structure of operations required to make an objective executable.

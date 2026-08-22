# Fresta Diamond — Implementation and Resumption Status

**Checkpoint date:** 2026-08-07  
**Implementation:** `diamond/src/fresta_diamond/`  
**Tests:** `diamond/tests/`  
**Architecture:** `diamond/docs/ARCHITECTURE.md`  
**Documentation map:** `diamond/docs/INDEX.md`  
**Ontological authority:** `ONTOLOGICAL_KERNEL-v3-DRAFT.md` (still a draft)

## 1. Purpose of this file

This is the short operational map for resuming Diamond work without rebuilding
the conversation. It records what actually runs, what the ontology permits us
to claim, known debts, and the next safe milestones. It does not supersede the
kernel or the architecture contract.

## 2. Current executable flow

```text
bounded objective + blueprint + input artifacts
  -> mandatory constitutional firewall attestation
  -> ModuleRegistry: exact enabled capability candidates
  -> Resolver: derive a typed dependency DAG (PROPOSED)
  -> PlanValidator: validate dataflow/contracts/policy (VALIDATED | REJECTED)
  -> EffectBroker: issue plan/node-scoped grants (AUTHORIZED | DENIED)
  -> Runtime: sequentially execute authorized nodes
  -> OntologyEvaluator: validate structural/constitutional evidence artifacts
  -> EpistemicEvaluator: validate claim-mode evidence burdens
  -> immutable output artifacts + distinct execution/closure axes
```

The controller is a dependency-injected façade over these phases. It contains
no provider-specific imports or command chains.

## 3. Implemented and tested

### Milestone 34 — persistent application composition

- Added a Diamond-owned application facade intended to be shared by future
  REPL and Web adapters; it has no Frankenstein imports or data dependency.
- A text learning candidate now persists its workspace revision, traverses the
  normal controller and bounded LLM evidence path, optionally repairs from
  typed remainders, and atomically commits Gatekeeper crystals plus PHI-minus.
- Reopening the same data root verifies and retrieves memory without repeating
  the model call.
- Explicit concept nomination consumes committed retrievable crystals and
  persists an order-free candidate; deterministic validation remains a
  separate operation.
- One persistent attention context can resolve exact learning-memory, concept,
  and workspace references before a bounded model response. Authority labels
  and continuation persistence remain enforced.
- Verification at this checkpoint: Diamond **208 passed**; full suite
  **395 passed**.

Remaining before an honest user interface: bounded automatic concept proposal,
objective-relative retrieval, automatic attention batch/sleep continuation,
document batching, and a shared command service. REPL and Web must remain thin
adapters over that service.

### Milestone 35 — bounded concept nomination

- A model may now nominate one concept or explicitly return `NO_CONCEPT` over
  committed ACTIVE crystals supplied in one scope.
- Trusted anchoring rejects invented memberships and parents. Only validated or
  crystallized existing concepts are offered as possible parents.
- Successful output remains `UNVALIDATED_CONCEPT_NOMINATION` and can create
  only a versioned `CANDIDATE`; validation and promotion remain separate.
- The isolated local-Qwen smoke completed two provisional learning commits and
  proposed one two-member candidate in three sequential tracked model calls.
- Verification: Diamond **212 passed**; full suite **399 passed**.

The next concept slice is evidence generation for the existing deterministic
concept validator. Automatic retrieval and batching remain prerequisites for a
general chat/learn interface.

### Milestone 36 — bounded concept evidence and deterministic promotion

- Added a separate controller-native evidence chain for an existing concept
  candidate: one bounded model proposal, deterministic epistemic derivation,
  and host-anchored derivation seals.
- The host restores the concept version, scope, analysis identity, member
  provenance, seal targets, source kinds, timestamps, and authority label.
  Invented crystals, provenance, or targets cannot become valid evidence.
- `DiamondApplication.evaluate_concept()` exposes the same persistent use case
  to future REPL and Web adapters. The model cannot write `VALIDATED` or
  `CONTESTED`; only `ConceptValidationService` may archive the report and create
  a new concept version.
- Complete closed evidence promotes a candidate through the deterministic
  validator. Missing or invented seal sources archive explicit remainders and
  leave the stored candidate unchanged.
- Verification: Diamond **217 passed**; full suite **404 passed**.
- Live-Qwen hardening found two transport defects without granting authority:
  a singleton object where the contract requires an array, then valid JSON
  followed by extra text. The prompt now carries an exact array-preserving
  response shape, and the bounded decoder consumes only the first complete
  JSON object. A later smoke stopped earlier because one learning candidate
  remained `DEFERRED`; concept nomination correctly refused fewer than two
  ACTIVE crystals. That run therefore could not demonstrate concept promotion;
  the isolated concept-evidence fixture below removed this confounder.
- Added that isolated fixture using two deterministically seeded ACTIVE
  crystals and exactly one local-model call. It exposed that ungrounded model
  `COUNTEREVIDENCE` could contest a candidate despite lacking a negative
  epistemic graph; this provider now rejects that contribution until a
  dedicated negative-evidence path exists. The final isolated
  `qwen/qwen3-14b` run completed with both closure axes true, no remainders,
  and a deterministic version-2 `VALIDATED` concept.

Next clean cut: objective-relative retrieval/batching for learning and concept
nomination, followed by automatic attention continuation. The shared command
service and thin REPL/Web adapters remain downstream of those core behaviors.

### Milestone 37 — external concept catalogs as revisable heuristics

- Added a strict `UNVALIDATED_CONCEPT_CATALOG` boundary for operator-supplied
  indexes. Catalog rows cannot contain validation refs, derivation seals,
  promotion authority, or intrinsic O1/O2/O3 assignments.
- Imported the supplied NotebookLM workbook as a Diamond-owned fixture with 17
  concept nominations, seven document references, exact spreadsheet row
  locators, and the source workbook hash. Document indices remain explicitly
  weaker than exact passage provenance.
- `ConceptCatalogIntake` stages each name as a workspace `CONCEPT` and each
  descriptive field as a `HYPOTHESIS`. It creates no crystal or
  `ConceptRecord`, and invokes no model.
- `DiamondApplication.stage_concept_catalog()` exposes this same safe intake to
  future interfaces. Later LLM work may revise, decompose, or reject the
  heuristics, but any accepted change must traverse `/learn`, evidence, and
  versioned concept validation.
- The copied catalog contains no external runtime path; package guards still
  reject every Frankenstein import or path back to the parent project.
- Verification: Diamond **223 passed**; full suite **410 passed**.

Next clean cut remains objective-relative catalog/memory retrieval. Selection
must be a weak-O2 nomination derived for the current objective, not lexical
similarity disguised as concept truth.

### Milestone 38 — objective-relative attention retrieval

- Added a bounded provider that may select exact existing roots from ACTIVE
  learning crystals, eligible concepts, latest cognitive sheets, and scoped
  Φ− observations for one declared objective. `NO_SELECTION` is a valid result.
- O1/O2/O3 assignments are contextual roles on the nomination, never intrinsic
  ranks written back to cards or concepts. The same exact root is tested as O1,
  O2, and O3 under three different objectives.
- The host rejects invented or duplicate references, invalid relevance, and
  empty/invalid roles. It restores kind and source authority from the trusted
  request; model output cannot validate, promote, merge, or rewrite an item.
- `DiamondApplication.retrieve_for_objective()` now creates an active attention
  revision and materializes the selected roots through the existing exact
  resolvers. Concept dependencies remain host-owned and dependency-closed.
- Retrieval uses neither Jaccard nor a fixed top-k. Candidate discovery is
  deterministic; selection is the bounded weak-O2 model nomination. Workspace
  summaries are discovery descriptors only, while selected sheets materialize
  their complete stored content.
- Verification: Diamond **231 passed**; full suite **418 passed**.

Next clean cut: bounded batching when candidate inventories exceed one model
window, followed by automatic attention sleep/resume. After those foundations,
the shared command service can expose the same application behavior to thin
REPL and Web adapters.

### Milestone 39 — sequential retrieval batching

- Objective-retrieval inventories are now partitioned deterministically by an
  estimated request-token budget. Batches preserve the original candidate
  order and contain every exact reference once; they are executed sequentially,
  never concurrently.
- No candidate is truncated to make it fit. A single descriptor larger than
  the declared batch budget fails explicitly, leaving future sheet/sleep
  decomposition to handle it without hidden information loss.
- The host conservatively unions batch nominations. `NO_SELECTION` in one
  batch cannot erase a justified selection in another; duplicate nominations
  preserve source identity and union contextual roles without promotion.
- `DiamondObjectiveRetrievalOutcome` exposes every batch result and total model
  call count. Attention context creation occurs only after all batches complete,
  so a failed batch cannot leave a partial ACTIVE context behind.
- Added `run_objective_retrieval_qwen.py`, which stages three isolated catalog
  sheets and makes exactly one live model call. `qwen/qwen3-14b` selected only
  the exact Three-Order Analysis sheet in 20.18 seconds; projection was READY,
  authority remained `UNVALIDATED_WORKSPACE_PROPOSAL`, and no remainder arose.
- Verification: Diamond **235 passed**; full suite **422 passed**.

Next clean cut: automatic attention sleep/resume and decomposition for one
oversized candidate. Concept nomination/evidence batching can then reuse the
same sequential pattern rather than create a separate orchestration path.

### Milestone 40 — budget sleep and atomic attention resume

- `DiamondApplication.attention_turn()` now detects a durably persisted pure
  `TOKEN_BUDGET` continuation and automatically creates a `SUSPENDED` attention
  revision linked to that exact checkpoint. The transition happens only after
  continuation persistence; no window-local state is treated as memory.
- `resume_attention()` verifies the checkpoint hash, exact source revision,
  latest suspension reason, and absence of blocked refs. It then atomically
  creates one `REACTIVATED` revision containing only pending refs, categorized
  again as source, validated, selected, workspace, or remainder evidence.
- A continuation checkpoint is single-use relative to the latest lifecycle:
  replaying it after reactivation is rejected and cannot rewind attention.
- A two-sheet regression proves partial response → automatic sleep → exact
  pending-only resume → READY response, with one model call per usable batch.
- If a required object is too large and no ref was completed, Diamond sleeps
  before any model call but rejects blind resume. It requires decomposition or
  an explicit strategy change, preventing an infinite wake/fail/sleep loop.
- `AttentionMemory.reactivate()` can now replace all reference categories in
  the same append-only revision, avoiding a crash window between reactivation
  and a separate update.
- Verification: Diamond **238 passed**; full suite **425 passed**.

Next clean cut: decompose one oversized workspace object into bounded child
sheets with exact parent provenance. A scheduler/chat adapter may then drive
the already-safe resume operation; concept nomination/evidence can reuse the
same batching lifecycle.

### Milestone 41 — hierarchical and dual-representation cognitive sheets

- Added hash-bound `SheetRevisionRef` targets. `scope-child` links must resolve
  to an existing exact revision and cannot form a self-hierarchy. A mother keeps
  the child revision it actually used even after that child evolves.
- `child_statuses()` and `MotherSheetService.snippet_statuses()` compare linked
  revisions with current child heads without mutating either history. Snippets
  are typed index elements with exact child provenance, not copied detail.
- Attention contexts may bind one exact `active_sheet_ref`. A scratch sheet may
  begin empty; application methods create it and advance sheet+attention through
  append-only revisions without any model call. Exact historical active sheets
  remain materializable rather than silently resolving to latest.
- Added `fresta-canonical@1`: an auditable working representation for objects,
  claims, dependencies, provenance, relations, heuristic confidence, and open
  questions. A sheet may pair it with human text carrying a declared language.
- Canonical JSON round-trips byte-stably. Its fixed authority is
  `UNVALIDATED_WORKSPACE_REPRESENTATION`; neither confidence nor a working claim
  can validate itself. A model-developed dialect remains hypothesis-only.
- Verification: Diamond **250 passed**; full suite **437 passed**.

Next clean cut remains deterministic decomposition of one oversized object into
ordered bounded child sheets and a mother index. Semantic/O3 refinement may be
layered later, but the first path must preserve every source byte and provenance.

### Milestone 42 — lossless oversized-object decomposition

- Added `SheetDecompositionService`: deterministic Unicode-safe partitioning
  into ordered child sheets under an explicit content-token budget.
- Every leaf records source reference, source SHA-256, ordinal and fixed
  `UNVALIDATED_WORKSPACE_DECOMPOSITION` authority. Concatenating exact leaf refs
  must reproduce the original hash before the operation reports success.
- Large child sets build bounded intermediate mother indexes recursively. All
  hierarchy edges remain revision+hash bound; later child revisions cannot
  rewrite an old decomposition.
- Preflight rejects sheet-ID collisions before the first append. Impossible
  whitespace-only partitioning fails explicitly instead of dropping bytes.
- Exact leaves materialize through the existing attention resolver. The leaf
  budget covers content only, so callers must reserve prompt metadata overhead.
- Semantic/O3 boundary refinement and automatic invocation by the scheduler
  remain separate future layers; no LLM call is needed for this invariant.
- Verification: Diamond **256 passed**; full repository **443 passed**.

Next clean cut: connect the no-progress oversized-attention remainder to this
decomposition operation, then resume over the generated exact child refs.

### Milestone 43 — automatic oversized-attention recovery

- A zero-progress sleep now detects one oversized workspace ref, decomposes its
  exact injected representation and reactivates the same task over bounded
  hash-bound leaves without requiring a model decision.
- The original required object becomes a continuation-governed sequence. Leaves
  are optional per prompt so batches can progress, while the immutable pending
  frontier preserves the complete sequence.
- Empty evidence progress is fail-closed: a PARTIAL projection containing only
  its base header cannot call the LLM.
- `auto_decompose=False` retains an explicit diagnostic/admin boundary. Unknown
  or non-workspace oversized refs are not silently transformed.
- An end-to-end test processes a 2,000-character sheet across repeated sleeps
  and resumes, proves every exact leaf is visited once, and reaches convergence.
- Verification: Diamond **257 passed**; full repository **444 passed**.

Next clean cut: expose a small command service over attention/create/turn/resume
and learn so a future REPL and Web adapter share exactly the same contracts.

### Milestone 44 — shared headless command boundary

- Added `CommandRegistry`, immutable specs/invocations/results and
  `DiamondCommandService`; no REPL or Web logic is embedded in the handlers.
- `/learn`, attention create/turn/resume/status and help call the existing
  persistent application methods rather than duplicating blueprints or stores.
- Text parsing and structured `invoke()` share one handler. A stable
  `encode_command_result()` creates the JSON-ready interface boundary.
- Specs declare whether a command may call the model; results report the actual
  call count, continuation checkpoint, authority and state.
- Name/alias collisions, unknown options, forged invocation/result identity and
  non-JSON payloads fail explicitly. A custom command registers without edits to
  the service or interface parser.
- Automatic attention decomposition is observable through the same command and
  returns its root ref plus pending continuation.
- Verification: Diamond **263 passed**; full repository **450 passed**.

Next clean cut: add a minimal configurable headless runner over the shared
service, then build the first REPL adapter without adding domain handlers.

### Milestone 45 — configured command runner and live smoke

- Added `CommandRuntimeConfig`, `build_command_service()` and `run_commands.py`.
  The runner requires an explicit Diamond data root and never infers production
  or Frankenstein state.
- Offline `/help` proves that constructing the OpenAI-compatible adapter does
  not contact its host unless a selected command actually needs the model.
- `CommandState.INCOMPLETE` now distinguishes a model attempt from a produced
  response artifact. The JSON payload exposes execution state and remainders;
  the runner exits `3` for incomplete work.
- A live Qwen smoke exposed this distinction at a deliberately tiny response
  budget. Retrying with 512 response tokens completed in one call with zero
  remainders through runner → commands → application → controller → broker.
- Verification: Diamond **267 passed**; full repository **454 passed**.

Next clean cut: implement a thin persistent-process REPL that delegates every
line to `DiamondCommandService`; do not add REPL-specific domain handlers.

### Milestone 1 — clean contracts and provider substitution

- Immutable boundary contracts for artifacts, manifests, operations,
  blueprints, plans, remainders, closure, and execution.
- Manifest lifecycle `discover -> verify -> enable`; handlers cannot be loaded
  before verification.
- The same controller and blueprint run with provider A and provider B without
  consumer changes.
- Missing, incompatible, or unauthorized providers never trigger a magic
  fallback.

### Milestone 2 — derived multi-node DAG

- A blueprint declares typed capability outcomes, not provider names.
- Requirements may be listed out of dependency order; the resolver derives a
  sequential topological order from named artifact schemas.
- Plan edges and intermediate artifact bindings are explicit.
- The validator reconstructs dependency edges and detects tampering.
- A dependency loop without an external foundation remains rejected with
  typed remainders.

### Milestone 3 — effect authorization

- Manifest effect declaration, blueprint permission, adapter availability, and
  runtime invocation are separate checks.
- `EffectBroker` issues immutable grants scoped to plan, node, module,
  operation, effects, and permissions.
- A handler invokes an injected adapter through `ExecutionContext.invoke()`.
- A declared and permitted effect is still denied when no adapter is installed.
- A handler cannot expand an effectless grant through the public context API.
- A validated plan cannot run without authorization for that exact plan.

Verification at this checkpoint: Diamond **108 passed**; full suite
**289 passed**. Production `data/` and Git were not touched.

### Milestone 5 — deterministic ontological witness validation

- Immutable records distinguish O1 manifestation, strong-O2 reciprocal
  relation, O3 constraint, FILTER, excluded cost, and constitutional grounding.
- Directions use computational stages:
  `OPENNESS -> FILTER -> OBJECT` and `OBJECT -> FILTER -> OPENNESS`.
- `OntologicalValidator` derives reciprocal, constitutional, and structural
  verdicts without consulting a model checkbox.
- Unused evidence, missing endpoints, empty witnesses, absent costs, scope
  mismatch, missing FILTER, and reversed directions become typed remainders.
- Advisory `closed=false` cannot reject a complete graph; advisory `closed=true`
  cannot close an incomplete graph.

### Milestone 6 — evidence-artifact integration

- Providers may produce `artifact://structural-evidence-graph@1`; the graph is
  part of normal typed dataflow rather than an out-of-band controller argument.
- A strict codec rejects malformed provider payloads visibly.
- `OntologyEvaluator` validates produced graphs after technical execution and
  attaches reports to `ControllerResult`.
- Structural and constitutional fields in `ClosureReport` are updated without
  conflating them with technical completion, operational convergence, or
  epistemic closure.
- A plan with no evidence artifact continues to report those axes as `None`.

### Milestone 7 — conditional constitutional depth

- `AnalysisDepth.CONTEXTUAL` is now the default for ordinary post-F objects.
- A contextual graph can close structurally without explicitly traversing Φ/F;
  its constitutional verdict remains `None` rather than false.
- `AnalysisDepth.CONSTITUTIONAL` requires an explicit grounding path.
- Reversed or missing grounding fails the constitutional axis without erasing a
  reciprocally valid contextual structure.
- Analysis depth is serialized in the evidence artifact and selected by the
  bounded objective, not inferred from a model's vocabulary.

### Milestone 8 — bounded local-Qwen runner

- Standard-library OpenAI-compatible adapter with fixed host/model, timeout,
  token ceiling, strict message validation, and injected transport for tests.
- `LlmEvidenceOperation` asks for the typed graph and restores trusted analysis
  ID, object, scope, and depth after the model response.
- Contextual mode strips attempted constitutional grounding from provider output.
- JSON extraction tolerates Qwen thinking blocks and Markdown fences without
  trusting surrounding prose.
- `run_qwen.py` builds a real module, blueprint, grant, controller execution,
  evidence artifact, and independent ontological verdict.
- The live model call is intentionally left for the user-run manual test.

### Milestone 9 — first live Qwen observations

- A contextual automobile run completed end-to-end with structural closure and
  an unevaluated constitutional axis.
- Its graph exposed semantic weakness despite valid shape: vague return witness
  and unsupported physical alternatives. This confirms that structural closure
  is not epistemic closure.
- A constitutional incompleteness run correctly exposed model-created nested
  scopes (`metaphysical`, `epistemology`) as `INVALID_SCOPE`.
- That run revealed and fixed an axis bug: constitutional closure can no longer
  be true when the local reciprocal structure is invalid.
- The constitutional prompt now defines OPENNESS/FILTER compactly and prohibits
  invented authors, theories, experiments, sources, and observations.
- A second constitutional run confirmed those repairs: trusted scope and
  provenance were preserved and both closure axes remained false when the local
  chain was invalid.
- The remaining failure was precise and repairable: the strong relation used
  constraint `c1` while its FILTER used `c2`, leaving selected evidence unused.
- The prompt now requires the relation and FILTER to share the exact O1/O3/cost
  triple, while the validator remains the authority if the model disobeys.

### Milestone 10 — bounded graph repair

- A separate `three-orders.repair-evidence@1` operation receives the rejected
  graph and deterministic remainders.
- Repair produces a complete new evidence artifact linked by
  `parent_artifact_id` and numbered attempt; it never mutates V1.
- Trusted object, scope, depth, and analysis identity are restored outside model
  authority.
- The manual runner accepts `--repair-attempts 0..3`, defaults to one, and stops
  immediately when a version closes structurally.
- Fake-provider tests cover lineage and remainder-bearing repair prompts.
- The first live bounded run closed at V1, correctly avoiding an unnecessary
  second model call.

### Milestone 11 — claim-mode epistemic evidence

- Added the independent schema `artifact://epistemic-evidence-graph@1`.
- Claims declare `OBSERVATION`, `ATTESTATION`, `DERIVATION`, `HYPOTHESIS`,
  `FORECAST`, or `INVARIANT`; grammatical confidence cannot choose the burden.
- Evidence events preserve source actor, exact locator, lineage, context,
  method, time, scope, and supporting or contradicting stance.
- Source actor, claim subject, and owner remain separate, preventing a document
  statement from silently becoming direct user identity.
- Deterministic burdens require the appropriate event or metadata for each
  claim mode. Invariants count independent lineages rather than copied sources.
- Live counterevidence and unused, cross-claim, malformed, or out-of-scope
  evidence remain explicit remainders.
- `EpistemicEvaluator` updates only `epistemic_closed`; structural and
  constitutional axes remain independent.
- A testable hypothesis may satisfy its mode burden without becoming an
  observation or a confirmed memory card.

### Milestone 12 — append-only execution journal

- Added an optional in-memory `EventJournal` with monotonic sequence, generated
  IDs, timestamps, plan correlation, subject references, and causal parents.
- Event payloads are deeply frozen snapshots; mutating the caller's original
  mapping cannot rewrite history.
- Unknown causal parents and duplicate generated IDs are rejected.
- The controller emits plan, authorization, ontological, epistemic, and final
  objective events.
- The runtime emits operation start, output, and failure events.
- The effect boundary emits request, commit, and rejection events without
  copying effect arguments into journal metadata.
- A shared journal isolates each controller call while preserving one global
  append order. `ControllerResult.journal_events` contains only that call.
- Journal injection remains optional, preserving existing controller behavior.
- Verification: Diamond **56 passed**; full suite **237 passed**.

### Milestone 13 — sealed historical journal archive

- Added optional `JsonlJournalArchive`; no path or file is created until an
  archive is explicitly injected and an execution is sealed.
- Each `fresta://journal-segment@1` contains one plan correlation and contiguous
  immutable events.
- Canonical JSON bodies are SHA-256 sealed and chained to the previous segment.
- Reload verifies hashes, schema, event contracts, correlation, and complete
  chain continuity; historical tampering is rejected visibly.
- Archived history is queried by correlation and is not automatically injected
  into model attention.
- Controller integration seals only the events appended by that execution.
- Archive failure after an output exists preserves the technical result, sets
  `operational_converged=false`, adds `EXTERNAL_UNCERTAINTY`, and records a
  volatile `JOURNAL_ARCHIVE_FAILED` event. Effects are not automatically
  repeated.
- Verification: Diamond **62 passed**; full suite **243 passed**.

### Milestone 14 — finite budget, checkpoint, and resume

- Added immutable `ExecutionBudget`; the first clock measures completed
  operations per episode and supports explicit unbounded execution.
- Runtime checks budget before each pending node and pauses without starting
  work it cannot complete inside the declared operation allowance.
- `BUDGET_EXHAUSTED` produces `ExecutionState.PAUSED`, open operational
  convergence, a typed remainder, and an immutable `RuntimeCheckpoint`.
- Checkpoints preserve plan, completed/pending frontier, intermediate artifacts,
  public outputs, prior checkpoint lineage, and the archived segment hash.
- `DiamondController.resume()` requires a fresh budget, revalidates current
  provider availability, reauthorizes effects, and skips completed nodes.
- Journal/archive history records checkpoint, pause, and resume across multiple
  segments sharing the same plan correlation.
- A three-node adversarial test completes across three one-operation episodes
  with every node executed exactly once.
- A provider disabled during sleep prevents continuation without erasing the
  valid earlier work or fabricating a fallback.
- Verification: Diamond **68 passed**; full suite **249 passed**.

### Milestone 15 — durable checkpoint workspace

- Added `fresta://runtime-checkpoint@1` with strict codecs for plans, nodes,
  edges, budgets, remainders, external/intermediate artifacts, outputs, and
  checkpoint lineage.
- `JsonCheckpointStore` creates no directory until an explicitly configured
  pause is persisted.
- Each checkpoint is stored once under its ID and sealed by SHA-256; overwrite,
  path traversal, malformed records, and historical modification are rejected.
- Checkpoint persistence requires a sealed journal archive and stores that
  segment hash with the active frontier.
- A simulated restart with new controller, journal, archive, and store objects
  loads the checkpoint and completes only the remaining nodes.
- Persistence failure preserves the volatile frontier, marks operational
  convergence false, returns `EXTERNAL_UNCERTAINTY`, and emits
  `CHECKPOINT_PERSISTENCE_FAILED`.
- The store remains isolated from production `data/` and is activated only by
  dependency injection.
- Verification: Diamond **71 passed**; full suite **252 passed**.

### Milestone 16 — executable anti-entropy admission

- Added immutable `ModuleDiscoveryEvidence`, `ModuleAdmissionPolicy`, and
  `ModuleAdmissionReport`.
- Discovery origin is loader-owned rather than a compatibility flag controlled
  by the candidate manifest.
- Community candidates require provenance plus a loader-verified SHA-256
  package digest.
- Protected kernel, validator, trust, journal, provenance, and direct-memory
  capability/effect/permission families are rejected for every source.
- Effectful community operations must declare a permission boundary and failure
  modes before executable handlers can be enabled.
- Rejection produces typed `POLICY_VIOLATION` remainders, moves the module to
  `REJECTED`, and prevents handler binding.
- Discovery/admission decisions emit `MODULE_DISCOVERED`, `MODULE_ADMITTED`, or
  `MODULE_REJECTED` without journalling package contents.
- Verification: Diamond **80 passed**; full suite **261 passed**.

### Milestone 17 — revisioned cognitive sheets

- Added typed `SheetElement`, `SheetLink`, `SheetRevision`, `SheetBacklink`, and
  `WorkspaceSelection` contracts.
- Sheet elements retain individual scope, provenance, kind, and contextual role
  nominations; a sheet is not validated as one indivisible block.
- Revisions are contiguous, extend only the latest parent, and move
  monotonically through `DRAFT -> STAGED -> PROPOSED`.
- `JsonlCognitiveWorkspace` is lazy, append-only, globally SHA-256 chained, and
  separately checks each sheet's parent hash.
- Current backlinks are derived from latest revisions while historical links
  remain available by explicit query.
- Selecting elements emits `artifact://workspace-selection@1` with authority
  fixed to `UNVALIDATED_WORKSPACE_PROPOSAL`.
- The workspace exposes no accepted/confirmed state or memory-promotion method;
  tampering and self-confirmation attempts are covered by tests.
- Verification: Diamond **88 passed**; full suite **269 passed**.

### Milestone 18 — workspace-to-learn bridge

- Added `WorkspaceLearnRequest` and the prefabricated
  `workspace.learn-proposal` blueprint.
- The blueprint requests `learn.prepare-proposal@1`; it does not name or import
  a concrete provider.
- A built-in deterministic provider passes through the normal
  `discover -> anti-entropy verify -> enable` lifecycle.
- The bridge checks selection, sheet, revision, objective, and fixed workspace
  authority before constructing a controller request.
- Output candidates remain `UNVALIDATED`, retain source identity and
  provenance, and explicitly require Gatekeeper, Three Orders, and epistemic
  evaluation.
- Technical intake completion leaves structural, constitutional, and epistemic
  closure unevaluated and grants no promotion authority.
- Fixed the central `Artifact` boundary to freeze nested mappings, sequences,
  and sets deeply; a proposal cannot be mutated into `ACCEPTED` after creation.
- Verification: Diamond **94 passed**; full suite **275 passed**.

### Milestone 19 — first LLM learning evaluation slice

- Added `learn.evaluate-proposal` over one bounded candidate scope.
- One LLM call proposes a coherent structural graph and epistemic assessment
  bundle; deterministic operations then fan out canonical structural and
  epistemic evidence artifacts.
- Trusted proposal ID, object, scope, candidate content, subject identity, and
  provenance remain outside model authority.
- Document provenance produces a document source actor rather than silently
  becoming user identity; hypotheses cannot be relabelled as observations.
- Unknown or missing candidate assessments remain explicit incomplete claims
  instead of destroying the raw bundle in a technical failure.
- Added `learn.repair-evidence-bundle`: a later call receives the prior bundle
  and exact validator remainders, with caller-bounded attempts.
- A live `qwen/qwen3-14b` run completed in one call with structural closure and
  epistemic closure as `ATTESTATION`; it correctly left constitutional closure
  unevaluated and performed no memory promotion.
- The live graph remained semantically somewhat vague despite valid structural
  form. This is preserved as a crystallization/quality limitation rather than
  hidden by the successful booleans.
- Verification: Diamond **101 passed**; full suite **282 passed**.

### Milestone 20 — deterministic crystallization Gatekeeper

- Added per-candidate `LearningCrystal` outcomes and an immutable
  `CrystallizationBatch`.
- `ATTESTATION`, `HYPOTHESIS`, and `FORECAST` with satisfied burdens become
  `PROVISIONAL`, never empirical confirmation.
- Resolvable missing evidence becomes `DEFERRED`; contradiction, invalid scope,
  policy failure, content rewrite, or trusted-boundary mismatch becomes
  `QUARANTINED`.
- `ACCEPTED` is reserved for stronger claim modes whose specific burden closes.
  No `CONFIRMED` state exists.
- `PHI_MINUS` is represented for the future negative boundary but is never
  emitted by default or used as a generic failure bucket.
- `JsonlLearningCrystalStore` accepts proposal plus `ControllerResult`, invokes
  the gate internally, links later crystals to prior versions of the same
  sheet element, and seals a global SHA-256 chain.
- The store is lazy, single-process, test-only, and disconnected from
  production `data/`.
- Diamond tests are now a package, preventing pytest module-name collisions
  with the Frankenstein suite.
- Verification: Diamond **108 passed**; full suite **289 passed**.

### Milestone 21 — isolated invariant regression laboratory

- Added a Diamond-owned `testdata/` tree with hashed fixtures, explicit
  baselines, and append-only run records.
- Deterministic replay uses the real workspace intake, controller, structural
  validator, epistemic validator, and crystallization Gatekeeper.
- Live mode swaps only the adapter and can call the local Qwen against the same
  cases.
- Comparisons exclude unstable prose, UUIDs, and timestamps. They retain
  closure axes, remainders, crystal outcomes, provenance actors/locators,
  document/user identity boundaries, and model call count.
- The first three cases cover a normal document attestation, a fictional
  character boundary, and invented structural provenance.
- Baseline promotion is deliberately absent from the runner: changed behavior
  must be reviewed and assigned a new baseline ID.
- Verification: Diamond **114 passed**; full suite **295 passed**; all three
  replay cases matched `learn-replay-v1`.

### Milestone 22 — first executable Φ− boundary memory

- Added immutable `PhiMinusObservation` and deterministic derivation after the
  crystallization Gatekeeper.
- `DEFERRED` is recorded as `INDETERMINATE` and never treated as a justified
  exclusion merely because evidence is missing.
- `QUARANTINED` and explicit `PHI_MINUS` outcomes become `EXCLUDED` observations
  with `phi_minus_justified=true`.
- The store reuses the sealed append-only journal archive and supports bounded
  retrieval by scope or candidate.
- Duplicate crystallization batches are rejected so one event cannot imitate
  independent recurrence.
- Persisted observations grant no promotion authority. Pattern aggregation,
  preflight feedback, and rule promotion remain disabled.
- Baseline v1 was preserved; `learn-replay-v2` adds the negative boundary and a
  structural-contradiction exclusion case.
- Verification: Diamond **120 passed**; full suite **301 passed**; all four
  replay cases matched `learn-replay-v2`.

### Milestone 23 — first Diamond ↔ Frankenstein comparison

- Added an external bridge runner that does not compromise the
  `fresta_diamond` package-import boundary.
- Each Frankenstein `/learn` run uses the centralized command registry,
  active blueprint execution, deterministic extraction replay, and a fresh
  temporary data root.
- A normalized contract compares dispositions, identity boundaries,
  epistemic states, persistence, and Φ− without equating internal schemas.
- Both systems preserve document/user boundaries in all four cases.
- Missing provenance is indeterminate in both systems.
- Diamond excludes the recorded O1/O3 structural contradiction; Frankenstein
  currently stores the candidate as `DEFERRED`.
- This is pipeline-capability comparison, not yet prompt/model parity: Diamond
  receives a recorded structural graph while Frankenstein receives its native
  candidate representation.
- Verification: Diamond **120 passed**; full suite **307 passed**; all four
  cross-system cases matched `cross-replay-v1`.

### Milestone 24 — atomic autonomous learning memory

- Added a single `LearningCommit` contract that preserves crystallization and
  its derived negative boundary together.
- Commits are prepared, flushed, fsynced, and atomically renamed into the
  committed directory.
- Interrupted finalization leaves a fully verifiable pending commit; a fresh
  memory instance can recover it without rerunning model or validation work.
- Duplicate proposal commits are rejected.
- Retrieval defaults to `ACCEPTED/PROVISIONAL`; deferred fallback and full
  exclusion audit require explicit policies.
- The Diamond benchmark now performs a real temporary autonomous-memory commit
  and reports positive, indeterminate, excluded, and Φ− counts.
- `learn-replay-v3` and `cross-replay-v2` preserve earlier baselines while
  recording the new behavior.
- Verification: Diamond **129 passed**; full suite **316 passed**; 4/4 cases
  matched each current baseline.

### Milestone 25 — native concept candidate foundation

- Added order-free `ConceptRecord`, intensional signatures, stateful
  memberships, aliases, parent links, and explicit lifecycle states.
- Candidates are built only from committed crystals admitted by an explicit
  retrieval policy; deferred evidence requires `FALLBACK`.
- A concept requires at least two distinct members and an intensional feature.
- The versioned store preserves identity across renames, rejects unknown
  parents and hierarchy cycles, and uses hashed Windows-safe filenames.
- Promotion is fail-closed: until a contextual concept-validation operation is
  installed, the store refuses `VALIDATED` and `CRYSTALLIZED` records.
- `learn-replay-v4` adds a canonical two-crystal automobile candidate and
  inherits the four immutable v3 projections.
- The test-only Frankenstein bridge now reads its own allowlist, so native
  multi-candidate fixtures cannot leak into the legacy comparison.
- Verification: Diamond **139 passed**; full suite **326 passed**; 5/5 Diamond
  cases matched `learn-replay-v4`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 26 — sealed internal concept validation

- Added field-level `DerivationSeal` contracts with typed sources and direct,
  synthesis, corroboration, or counterevidence contributions.
- Added deterministic `ConceptValidator`, reusing the existing structural and
  epistemic validators rather than trusting an LLM closure boolean.
- Validation binds concept version, scope, analysis, committed provenance,
  active member crystals, signature parts, and membership targets.
- `ConceptValidationReport` keeps local fit, structural support, definition,
  and external recognition as separate axes.
- Complete internal evidence versions a candidate to `VALIDATED`; finite gaps
  leave it unchanged; live counterevidence versions it to `CONTESTED`.
- Reports are hash-sealed and archived before the concept version. Public
  store writes still cannot fabricate a validated record.
- Unlearned web references are rejected. A future web source must first enter
  `/learn` and survive in committed-crystal provenance.
- `learn-replay-v5` adds a derived automobile-validation fixture without
  modifying the v4 candidate fixture.
- Verification: Diamond **147 passed**; full suite **334 passed**; 6/6 Diamond
  cases matched `learn-replay-v5`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 27 — brokered external concept research

- Added searchable concept gaps and a bounded neutral-first query planner.
- Added `workspace.research-concept` through the normal registry, resolver,
  validator, controller, and `EffectBroker`.
- The operation requires `internet.search:concept`; without an installed
  adapter authorization is denied before execution.
- Search results are bounded, deduplicated, hash-addressed source units with no
  promotion authority.
- Unknown query IDs, malformed URLs, oversized plans, and a candidate-label
  query outside the final position fail closed.
- Source units stage as external notes in the Cognitive Workspace, then produce
  an `UNVALIDATED_WORKSPACE_PROPOSAL` handoff for `/learn`.
- Added an optional HTTPS-verifying Wikipedia adapter. A real temporary smoke
  test reached Portuguese Wikipedia and retrieved “Automóvel”; no project data
  was persisted.
- `learn-replay-v6` records the complete candidate → validation → research →
  workspace handoff without adding the research fixture to the legacy bridge.
- Verification: Diamond **155 passed**; full suite **342 passed**; 7/7 Diamond
  cases matched `learn-replay-v6`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 28 — learned external recognition

- Added `ConceptSourceLearner`, which stages every source unit and executes the
  ordinary workspace → `/learn` → LLM evaluation → atomic commit path.
- Added a deterministic recognition validator that accepts only the canonical
  autonomous-memory commit and preserves URL, source-unit, scope, and concept
  version boundaries.
- Recognition and external definition are independent axes. Deferred evidence
  remains indeterminate; quarantined or Φ− evidence is contested.
- Supported external evidence creates a new validated concept version with
  paired `MEMORY_CRYSTAL` and `WEB_SOURCE` derivation sources. It does not
  revisit or weaken local fit.
- Recognition reports are hash-sealed and archived even when evidence is
  insufficient and no new concept version is created.
- `learn-replay-v7` records the full internal learn → concept validation →
  external research → external learn → recognition cycle.
- Verification: Diamond **161 passed**; full suite **348 passed**; 8/8 Diamond
  cases matched `learn-replay-v7`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 29 — source diversity and bounded stopping

- Added a typed, deterministic external-evidence policy separate from search,
  learning, and concept authority.
- Different URLs count as independent only across different normalized source
  families; language or content subdomains of one publisher count once.
- Coverage requires source count, publisher-family diversity, a neutral query,
  and a label query. The report preserves every unmet requirement.
- Bounded stopping distinguishes `CONTINUE_RESEARCH`, `STOP_SUFFICIENT`,
  `STOP_BUDGET`, and `REVIEW_CONFLICT`; it never means complete knowledge.
- Conflict overrides apparent sufficiency. Quantity cannot vote away a
  structural or epistemic exclusion.
- `learn-replay-v8` records four independent source families and an explicit
  `STOP_SUFFICIENT` result.
- Verification: Diamond **168 passed**; full suite **355 passed**; 8/8 Diamond
  cases matched `learn-replay-v8`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 30 — multi-context attention lifecycle

- Added an append-only, hash-chained attention store over references to existing
  checkpoints, sheets, sources, validated objects, selections, and remainders.
- The store permits one active foreground while preserving any number of
  suspended, archived, or abandoned contexts.
- Reactivation is an audited transition back to `ACTIVE`, not a permanent
  pseudo-state.
- `ARCHIVED` preserves completed history. `ABANDONED` records a path that must
  not continue, its reason, reuse policy, and optional successor.
- Controlled restart supports `NOTHING`, `SOURCES_ONLY`, `VALIDATED_ONLY`,
  `SELECTED_ITEMS`, and `FULL_CHECKPOINT`.
- Restart prepares a suspended successor before abandoning the predecessor and
  activating the clean path; invalid selections fail before any partial write.
- Attention has fixed projection-only authority and cannot validate referenced
  content.
- Verification: Diamond **178 passed**; full suite **365 passed**; 8/8 Diamond
  cases matched `learn-replay-v8`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 31 — bounded dependency-closed attention projection

- Added an objective-relative projector over candidates explicitly nominated by
  the active attention context.
- Objective, scope, and checkpoint summary form the constitutive base;
  checkpoint, active remainders, and selected items are mandatory references.
- Candidate dependencies are selected before their root and enter as one
  budget group. A root never enters without its available justification chain.
- Contextual O1/O2/O3 roles remain visible annotations, not intrinsic order or
  authority rankings.
- Scope mismatches, invalid evidence states, dependency cycles, duplicate or
  unnominated candidates fail closed or remain explicit unresolved refs.
- `READY`, `PARTIAL`, and `BLOCKED` distinguish complete projection, usable
  batching, and unsafe injection.
- Partial/blocked results emit a deterministic continuation checkpoint with
  completed, pending, blocked refs and typed reasons.
- Verification: Diamond **187 passed**; full suite **374 passed**; 8/8 Diamond
  cases matched `learn-replay-v8`; 4/4 bridge cases matched `cross-replay-v2`.

### Milestone 32 — exact attention reference materialization

- Added store-specific resolvers for versioned concepts, autonomous learning
  crystals, Φ− observations, Cognitive Workspace sheets, runtime checkpoints,
  and their active remainders.
- Resolution is exact and objective-bounded. It does not perform hidden
  semantic retrieval or let a store nominate additional roots.
- Concept membership dependencies are discovered transitively and supplied to
  the projector before their concept root.
- Scope, provenance, evidence state, and authority remain those of the source
  store; attention cannot promote or validate an object.
- Missing, wrong-scope, ineligible, ambiguous, and corrupted-store outcomes
  remain typed diagnostics. Mandatory missing refs block injection.
- Raw source URLs remain unresolved until a verified source catalog exists;
  URL text is never fabricated into source content.
- Verification: Diamond **194 passed**; full suite **381 passed**; the existing
  v8 and cross-v2 baselines remain unchanged because this cut is deterministic
  and does not call the LLM.

### Milestone 33 — durable continuation and bounded attention turn

- Added immutable, canonical JSON persistence for attention continuation
  checkpoints with content-hash verification and lookup by context revision.
- The controller derives a two-operation chain: deterministic prompt
  preparation followed by an explicitly authorized `llm.generate`.
- Preparation verifies the latest exact attention revision, enforces a
  configured token ceiling, resolves stores, projects dependencies, and
  persists continuation before permitting model execution.
- `BLOCKED`, stale, oversized, or non-durable partial contexts never call the
  model. `READY` and durably preserved `PARTIAL` projections may proceed.
- Projected text is marked as evidence/data rather than system instruction.
  A separately derived `TRUSTED_AUTHORITY_MANIFEST` is the only prompt region
  allowed to classify authority/evidence; content cannot promote itself.
  Model output remains `MODEL_RESPONSE_UNVALIDATED`.
- Added `run_attention_qwen.py` for an isolated manual live path.
- Live verification with `qwen/qwen3-14b`: one observable call completed over
  a `PARTIAL` projection after persisting its continuation; the answer
  correctly distinguished an unvalidated workspace note from established
  knowledge.
- A live adversarial note initially confused the model by claiming
  `VALIDATED_MEMORY` inside its body. After separating trusted metadata into
  the manifest, the same attack was repeated and the model correctly retained
  `UNVALIDATED_WORKSPACE_PROPOSAL` / `UNVALIDATED_WORKSPACE`.
- Verification: Diamond **204 passed**; full suite **391 passed**; 8/8 Diamond
  replay cases and 4/4 bridge cases remain matched to v8/cross-v2.

### Milestone 46 — bounded autonomous module-design proposals

- Missing-capability evidence can now enter a reuse-first module-design path.
  Exact providers produce deterministic `NO_NEW_MODULE` without calling the
  model; compatible output schemas remain candidates rather than proof.
- The LLM may choose `NO_NEW_MODULE` or propose one O1/O2/O3 operation design.
  Capability, schemas and `BELOW_CONTROLLER` layer are anchored by the host.
- Proposed effects and permissions must be subsets of host-supplied boundaries,
  empty by default. Attempts to replace controller, Gatekeepers, EffectBroker
  or blueprints are rejected by the anti-entropy preflight.
- Decisions are immutable and hash-verified, including rejected designs. Their
  authority remains `UNVALIDATED_MODULE_DESIGN`; no Python code is generated,
  installed, admitted or enabled.
- Added shared `/module suggest`, `/module proposals`, and `/module inspect`
  commands. REPL/Web remain pending and will only render this service.
- Live `qwen/qwen3-14b` verification made one sequential call, respected empty
  effect/permission boundaries and conservatively returned `NO_NEW_MODULE`.
  Its claim that empty effects imply no useful computation is a model-quality
  limitation, not a host-authority escape.
- Verification: Diamond **282 passed**; full suite **469 passed**.

### Milestone 47 — thin persistent REPL

- Added `DiamondRepl` and `run_repl.py` over one long-lived application and
  command service. No cognitive command handler is duplicated in the interface.
- TTY sessions receive a prompt; piped sessions receive uncontaminated JSON,
  optionally one compact object per line.
- Invalid commands, adapter failures and `KeyboardInterrupt` do not destroy the
  session. EOF and local exit commands terminate cleanly.
- Persistent-state coverage creates an attention context and reads the same
  foreground context on the following line through one service instance.
- A live Qwen REPL smoke made one model call. The model omitted `determinism`,
  so the host honestly returned `INCOMPLETE`; the following offline command ran
  successfully in the same process. The interface did not fabricate closure.
- Verification: Diamond **287 passed**; full suite **474 passed**.

### Milestone 48 — shared concept command surface

- Added read-only concept list/inspect plus bounded nominate/evaluate commands
  to the same registry used by REPL and structured invocation.
- Exact-version inspection verifies concept lineage before exposing history.
  Listing may filter latest/all versions, scope, and state without model use.
- Nomination retains `UNVALIDATED_CONCEPT_NOMINATION` and persists at most one
  `CANDIDATE`; evaluation routes model evidence through the existing
  deterministic validator and cannot accept a model-declared final state.
- A replay command test traverses two learns, nomination and validation through
  four tracked model calls. Textual list and structured `invoke()` return the
  same records. An offline real-REPL smoke exposed the commands with zero calls.
- Verification: Diamond **289 passed**; full suite **476 passed**.

### Milestone 49 — mandatory constitutional analysis binding

- Every controller analysis now opens only after the constitutional firewall
  binds its objective; every `ControllerResult` carries the resulting immutable
  attestation.
- Explicit firewall absence fails during controller construction. Presence and
  constitutional validity are no longer inferred merely from technical
  completion.
- The journal records the constitutional condition before plan proposal and
  preserves the causal chain through execution and resume.
- All controller instances created by the persistent application reuse the same
  mandatory boundary.
- Verification: Diamond **294 passed**; full suite **481 passed**.

### Milestone 50 — bounded semantic firewall intake

- Internal signals can now activate a contextual firewall review without
  receiving authority to deny by themselves.
- A typed semantic proposal supplies O1/O2/O3 context; the host maps that
  proposal to safe transformation, quarantine or denial.
- Missing, failed or malformed required semantic review fails closed into
  quarantine. Ordinary objectives do not call the analyzer.
- An operational bypass request is denied when context confirms it, while the
  same language presented for legitimate critical analysis may execute as a
  safe reference.
- A regression found that “Reject invented provenance” was initially confused
  with an imperative request. The trigger was narrowed and the full learning
  suite now preserves that counterexample.
- Verification: Diamond **299 passed**; full suite **486 passed**.

### Milestone 51 — brokered model review and first adversarial cycle

- Semantic review now executes as a typed, controller-native operation with one
  bounded `llm.generate` effect. The suspicious object is carried as inert data;
  the internal objective does not recursively replay it.
- The persistent application uses the configured model through the same shared
  call ledger, so firewall and task calls are counted together.
- Model output cannot grant authority or smuggle effects. It can only populate
  the semantic proposal consumed by the host decision.
- Initial deterministic red-team coverage exposed broad paraphrase gaps and
  improved risk nomination from 2/10 to 10/10 in that local corpus. A resulting
  false positive over a legitimate unvalidated nomination was then removed.
- Sequential local-Qwen contrasts passed 8/8: operational cases were denied and
  critical, defensive or fictional references were safely transformed.
- Verification: Diamond **308 passed**; full suite **495 passed**.

### Milestone 52 — inert recovered-data boundary

- Every `llm.generate` effect now crosses one host-enforced prompt boundary,
  including modules executed outside the persistent application.
- Runtime documents, cards, concepts, retrieval results and attention sheets
  are serialized as inert data. Their contents cannot create or terminate a
  host envelope and carry no instruction authority.
- The previous `trusted_*` prompt labels were removed. Host-anchored identity
  and scope remain protected by decoders and validators, while natural-language
  content remains evidence to assess rather than trusted instruction.
- Direct calls with unframed runtime text, data in the system role, malformed
  envelopes or text escaping an envelope fail before the model adapter runs.
- A live sequential Qwen adversarial artifact initially exposed semantic
  authority laundering despite correct technical framing. The evidence
  contract was tightened to require attributed source claims; the repeated
  run kept the hostile request attributed to its document and rejected its
  unsupported authority/promotion claim.
- Verification: Diamond **314 passed**; full suite **501 passed**.

### Milestone 53 — source-attribution closure guard

- Deterministic risk nomination now creates a host-owned source attestation;
  the model cannot add, remove or choose its handling requirement.
- A risk-bearing source may still be analyzed and retained, but structural
  closure requires O1 to keep the claim explicitly attributed to that source
  and O2/O3 to state an unambiguous authority/validation limitation.
- Wording such as “without kernel validation” is not accepted as a limitation:
  it may describe the requested bypass itself. Accepted limitations must state,
  for example, that the claim has no authority, cannot promote itself or lacks
  corroborating evidence.
- This guard does not decide general empirical truth. It prevents one narrower
  provenance error: converting “the source claims X” into “the system accepts
  X”, preserving the kernel distinction between coherence and truth.
- The live adversarial cycle rejected both V1 and its single repair attempt.
  The model repeated the invalid authority relation, so the bounded analysis
  remained honestly open rather than fabricating convergence.
- Two runner/repair defects exposed by the live cycle were fixed: immutable
  nested mappings now serialize recursively, and frozen remainder tuples are
  accepted by the repair operation.
- Verification: Diamond **319 passed**; full suite **506 passed**.

### Milestone 54 — controlled contaminated `/learn` and kernel catalog

- An isolated mixed-document fixture contrasts a reported control fact, a
  reported false fact, a fictional user-identity trap and an indirect
  constitutional instruction without touching operator documents or data.
- The first live sweep remained safe but exposed a response-contract ambiguity:
  Qwen nested `candidate_assessments` inside a redundant wrapper, leaving all
  ordinary candidates deferred. The prompt now forbids that shape and the
  decoder normalizes only that exact known wrapper.
- Epistemic classification now uses a kernel-owned catalog. The model analyzes
  freely, then selects one canonical `classification_id` with its computational
  meaning and per-intake availability, or `DEFER`; it may not invent labels.
- A repeated live false-fact test returned `classification_id=ATTESTATION`,
  structural and epistemic closure, and a `PROVISIONAL` crystal in one call.
  Diamond retained “the document reports this” without validating the false
  geographic content as observation or accepted truth.
- Constitutional source instructions are analyzed and then deterministically
  quarantined for later review, preserving provenance rather than deleting the
  source or making it active memory.
- The full four-case live comparison stayed safe. Two ordinary cases remained
  deferred because Qwen produced mechanically incomplete O1/O2/O3/FILTER
  graphs after one repair; finite structural-link choices are the next catalog.
- Verification: Diamond **323 passed**; full suite **510 passed**.

### Milestone 55 — canonical structural assembly

- Structural evidence now offers a kernel-owned `SINGLE_WITNESS_CHAIN` or
  explicit `DEFER_STRUCTURE` selection. The model still writes the semantic
  O1/O2/O3 witnesses, constraint, excluded cost and FILTER justification.
- The host deterministically creates IDs and connects manifestation, relation,
  constraint, FILTER and excluded cost. Mechanical identifier mistakes can no
  longer masquerade as failures of ontological reasoning on this path.
- A separate canonical source-authority choice distinguishes ordinary
  attribution, untrusted self-authority claims and deferral. Selecting an
  untrusted self-authority claim materializes the kernel limitation; a wrong
  choice is still rejected by the independent attribution validator.
- Legacy full-graph output remains accepted as a transition path; it is not
  used as the preferred provider contract.
- Live control `/learn`: one call, zero repairs, both closures true and a
  `PROVISIONAL` `ATTESTATION`. Live injection: one call, zero repairs, both
  closures true, correctly understood structure, but crystal remained
  `QUARANTINED` by constitutional source review.
- Verification: Diamond **327 passed**; full suite **514 passed**.

### Milestone 56 — remainder-relative repair actions

- Every learning repair remainder now carries a bounded action catalog relative
  to its kind and description. The model must choose one exact action per
  target and justify it; `DEFER_REPAIR` is always available.
- Actions cover redundant evidence, canonical rebuilding, trusted boundaries,
  constitutional direction, contradictory witnesses, source attribution,
  untrusted self-authority and epistemic reclassification.
- Selected actions are archived with validation errors. They express the
  repair decision but never prove that it succeeded; the structural and
  epistemic validators remain the only closure authorities.
- `CLASSIFY_UNTRUSTED_SOURCE` feeds the canonical source-authority compiler.
  `DEFER_REPAIR` forces an explicitly open structural result instead of
  fabricated convergence. Older repair responses remain readable during the
  transition and are marked as lacking the action array.
- Added an isolated live runner for a deliberately rejected legacy bundle.
  Qwen selected `REVISE_EPISTEMIC_CLASSIFICATION`, changed unsupported
  `OBSERVATION` to `ATTESTATION`, and closed both axes in one call with no
  action errors.
- Verification: Diamond **328 passed**; full suite **515 passed**.

### Milestone 57 — shared repair kernel and canonical concept evidence

- The remainder-relative catalog and action validator now live in the small
  shared `repair_policy` module. Learning and general Three-Order repair use
  the same policy rather than parallel hard-coded chains.
- General evidence repair now requires and archives one allowed action per
  remainder. Source classification and explicit deferral feed the canonical
  compiler; validators still retain closure authority.
- A live constitutional repair selected `REBUILD_CANONICAL_CHAIN`, restored
  the fixed grounding/analysis directions, and closed structural plus
  constitutional validation in one call with no action errors.
- Concept evidence now also prefers `SINGLE_WITNESS_CHAIN`: the model writes
  semantic witnesses while the host owns graph IDs and links. Legacy concept
  graphs remain accepted during transition.
- Live concept evidence closed both controller axes with the canonical shape,
  but the concept correctly stayed `CANDIDATE`: the model omitted an unsupported
  positive seal for one exclusion. This is a real evidence gap suitable for
  later research, not a mechanical repair target.
- Verification: Diamond **330 passed**; full suite **517 passed**.

### Milestone 58 — targeted concept-gap resolution

- Concept validation remainders can now generate a research request limited to
  the exact missing signature parts. A missing exclusion seal, for example,
  produces only a bounded boundary query; the concept label is not silently
  broadened into unrelated searches.
- `DiamondApplication.resolve_concept_gaps()` composes the existing research,
  ordinary `/learn`, versioned concept revision, and concept-evaluation paths.
  External text never seals or promotes a concept directly.
- Only crystals admitted to ACTIVE memory by `/learn` may become new concept
  members. Empty search results or learning without an active crystal stop the
  path safely and preserve the current candidate.
- A deterministic end-to-end test proves the full sequence: missing evidence,
  targeted search, source artifact, `/learn`, candidate revision, and fresh
  deterministic validation.
- The concept-evidence runner gained `--resolve-gaps`. In the latest live smoke,
  Qwen closed the original concept in one call, so research was correctly not
  invoked: version 2 became `VALIDATED`, with no remainders.
- Verification: Diamond **332 passed**; full suite **519 passed**.

### Milestone 59 — concept resolution on the shared command surface

- Added `DiamondApplication.evaluate_and_resolve_concept()`. It evaluates once
  and derives gap resolution only from an exact targetable validation
  remainder; interfaces do not encode the operation chain.
- Added `/concept resolve [--objective TEXT] [--queries N] [--results N]
  CONCEPT_ID` and the equivalent structured `invoke("concept.resolve", ...)`.
- If evaluation closes immediately, the command performs no search. If a
  targetable seal gap remains, it reuses targeted research, ordinary `/learn`,
  candidate revision and deterministic re-evaluation. An unresolved candidate
  is reported as `INCOMPLETE`, never disguised as completion.
- The command exposes bounded audit metadata without returning source text:
  request/query IDs, whether source units existed, learning commit, revised
  concept reference, initial validation and optional re-evaluation.
- Offline REPL `/help` exposed the new command with zero model calls; REPL code
  required no cognitive handler change.
- Verification: Diamond **332 passed**; full suite **519 passed**.

### Milestone 60 — objective retrieval and active workspace commands

- Added `/attention retrieve` (plus `/retrieve`) over the existing
  `retrieve_for_objective()` application path. It exposes bounded selection,
  contextual roles, exact materialization, projection state and continuation
  without putting retrieval logic in the interface.
- Added command-friendly application methods to start, resolve and append an
  active sheet. `/workspace create`, `show` and `append` preserve exact
  revision ancestry and update the attention pointer without model use.
- Command payloads omit projected source content while retaining refs,
  authority, epistemic state, contextual roles, dependencies and token cost.
- Deterministic tests prove an exact workspace ref can be nominated as O2 for
  one objective and injection-ready within budget. Separate lifecycle coverage
  proves revision 1 remains archived after append creates revision 2.
- Offline REPL `/help` inherited all four commands without any REPL cognitive
  code change or model call.
- Verification: Diamond **334 passed**; full suite **521 passed**.

### Milestone 61 — persistent chat spine

- Added a dedicated lazy `data-root/chat/` store. Session bindings are sealed;
  per-session messages form a verified SHA-256 chain with strict sequence,
  identity, role and authority checks.
- A chat binds one session to one attention context and one active transcript
  sheet. User and assistant messages are typed workspace elements, while the
  canonical chat history remains independent of memory promotion.
- `start_chat()` performs objective retrieval when eligible roots exist. An
  empty inventory is detected deterministically and starts clean attention
  with zero model calls rather than asking the model to fabricate refusal.
- `chat_turn()` persists the user message before bounded attention and retains
  any model response as `MODEL_RESPONSE_UNVALIDATED`; no learning commit or
  profile update occurs.
- Added `/chat start`, `say`, `status`, and `list` to the shared command service.
  REPL/Web require no cognitive chat handler.
- Tests cover restart/reload, tamper detection, duplicate IDs, empty retrieval,
  end-to-end attention/transcript behavior, command parity, and absence of
  implicit learning.
- Honest remaining gaps: per-turn retrieval, sleep/transcript resynchronization,
  chat lifecycle commands, encryption/retention, user profile, assistant
  personality, reflection, and natural module requests.
- Verification: Diamond **340 passed**; full suite **527 passed**.

### In-progress checkpoint — separated profile contracts

- Added `UserProfileClaim` and `AssistantPersonalityTrait` as distinct
  versioned proposal contracts. Neither has memory, profile-activation, or
  kernel authority.
- User claims are fixed to `actor:user` and accept only explicitly user-bound
  provenance. Documentary/Web first person cannot construct a profile claim.
- Assistant traits are fixed to `actor:assistant` and remain collaboration
  heuristics; kernel provenance and intrinsic ontological rank are excluded.
- Strict codecs preserve basis, confidence, scope, provenance, state,
  rationale, sensitivity where applicable, and predecessor lineage.
- Focused verification: **4 profile-contract tests passed**. The last complete
  verified baseline remains **340 Diamond / 527 total**; the full suite has not
  yet been rerun after this in-progress slice.
- Still WIP: sealed stores, public proposal/inspection paths, Gatekeepers,
  profile projection into chat, conditional reflection, correction/deletion,
  sensitivity policy, and encryption/retention.

## 4. Ontological alignment and claim boundary

- The objective supplies the bounded object of analysis.
- Modules, operations, cards, and concepts have no intrinsic universal order.
- A blueprint may record contextual O1/O2/O3 role nominations for its current
  objective. Those labels alone do not establish structural closure.
- Registry matching and semantic nomination are weak-O2 candidacy, not truth.
- Technical plan validity, authorization, technical completion, operational
  convergence, structural closure, constitutional closure, and epistemic
  closure remain separate axes.
- Successful DAG execution without a witness graph reports structural and
  constitutional closure as `None`. A contextual graph may establish structural
  closure while leaving the constitutional axis unevaluated; only explicit
  constitutional depth evaluates Φ/F grounding.
- PHI is constitutional incompleteness. A missing capability, input, adapter,
  permission, or finite item of evidence is a typed finite remainder, not PHI.
- Budget exhaustion will later produce a checkpoint/pause, never a PHI fixed
  point or fabricated convergence.

## 5. Known honest limitations

1. `Remainder` and `RemainderKind` are now canonical. Temporary `PhiRemainder`,
   `PhiKind`, `.phi`, and `.phi_id` read/import aliases remain for the
   pre-persistence transition; canonical constructors and internal execution use
   `remainders` and `remainder_id`.
2. Source-level isolation is guarded: Diamond imports neither `fresta` nor
   project-relative Frankenstein paths. Local-LLM, autonomous-memory and
   bounded concept-research paths now exist, but full functional autonomy still
   lacks production interfaces and broad external adapters.
3. `PlanValidator` intentionally validates technical DAG closure and policy.
   The controller now sends typed evidence artifacts to the separate
   `OntologicalValidator`; ordinary contextual role nominations still never
   imply closure.
4. The ontological validator proves contextual graph form, reciprocity, scope,
   and cost. The epistemic validator now proves minimum typed evidence burdens,
   not semantic truth. Neither validator can establish that arbitrary
   natural-language content corresponds to reality without trustworthy parsed
   evidence and appropriate external checks.
5. Contextual roles stored in plans remain nominations. They become structural
   evidence only through an explicit witness graph.
6. Operations are currently unary and outputs must have unique blueprint names.
   Fan-in, fan-out, alternatives, and bounded sub-blueprints remain pending.
7. Execution is sequential and now supports an operation-count budget, durable
   checkpoint, and cross-process resume. There are no retries,
   token/time/energy budgets, cancellation, or automated sleep policy yet.
8. Effects are mediated by the public in-process API, not securely sandboxed
   against hostile Python introspection. Strong isolation requires subprocess
   or RPC boundaries.
9. Effect adapters receive the grant and are responsible for enforcing
   resource-level details such as an allowed host or path.
10. The bounded local-LLM path is live-verified; isolated `/learn` commits to
   autonomous memory; bounded Wikipedia concept research and one bounded
   attention-turn blueprint are available. A thin REPL now exists. Source
   catalogs, Web, and production data remain disconnected.
11. Journal history, checkpoints, and cognitive sheets can persist, but repair
   artifacts still do not have their own durable store.
12. The JSONL archive is single-process, verifies by reading its chain, and has
   no large-history index, encryption, compaction, or cross-process lock yet.
13. Checkpoint files currently embed provisional artifact payloads. There is no
    encryption, external blob store, retention policy, or per-artifact
    redaction yet.
14. Anti-entropy admission validates observable declarations and trusted loader
   evidence. It does not inspect hostile bytecode, verify signatures, or provide
   an in-process security sandbox.
15. `ONTOLOGICAL_KERNEL-v3-DRAFT.md` Part V is still planned. The Diamond is
   experimental evidence for that future computational constitution, not an
   amendment to it.
16. The firewall establishes mandatory presence, attestation and a brokered
    semantic decision path. Retrieved/document content now has a mandatory
    inert prompt boundary, but broad semantic adversarial coverage, output
    truth validation and release hardening remain WIP. This is not yet a
    production-security claim.
17. Source-attribution validation currently activates only for deterministically
    nominated constitutional risks. It is intentionally not a general semantic
    truth oracle; broader contradiction and domain-truth review still requires
    typed evidence, external checks or bounded model-assisted analysis.

## 6. Recommended next milestones

1. **Complete profiles and chat reflection:** the first persistent central chat
   path and the separate profile/personality contracts now exist. Add their
   versioned stores, Gatekeepers and inspection; then connect conditional,
   source-bound post-turn reflection. Natural-language capability requests may
   reuse `module.suggest`, but cannot install or authorize modules.
2. **Versioned `/brain analyze`:** create a deterministic system inventory,
   bounded Three-Order diagnosis, immutable reports and non-executing proposals
   for heuristic revision, concept/card maintenance, workspace investigation,
   or reuse of `module.suggest`. Kernel invariants and model weights remain
   outside this mutation boundary.
3. **Document `/learn` orchestration:** add source-file intake, deterministic
   batching and resumable convergence over the existing candidate pipeline;
   do not create a second learning implementation in the interface.
4. **Φ− pattern memory:** aggregate independent exclusions, including module
   admission failures, retrieve relevant patterns for preflight/repair, and
   prohibit automatic kernel promotion.
5. **Cross-system learning comparison:** add a normalized Diamond ↔
   Frankenstein quality suite for cards and concepts. The Diamond-only
   invariant baseline now exists; neither system may share runtime state.
6. **Anti-entropy continuation:** connect crystallization decisions to the
   anti-entropy audit and add isolated loading/signature policy before real
   community code is accepted.
7. **General DAG:** multi-input operations, fan-in/fan-out, explicit completion
   outcomes, alternatives, cost, and bounded sub-blueprints.
8. **Pre-Web connection map:** document each command's objective, application
   method, blueprint, effects, stores, authority, sleep behavior and output.
9. Add Web only after the REPL proves the persistent adapter and the connection
   map is reviewed; both interfaces
   must call the same command service and controller contracts.
10. **Workspace Agent mode:** after the thin Web chat path is proven, expose
    project-scoped plans, file reads, patches, tests, diffs, approvals and
    resumable checkpoints through the same controller, firewall and
    `EffectBroker`. Never turn the browser into a second agent runtime.

## 7. Resume checklist

1. Read `diamond/README.md`, then this file and the architecture sections
   relevant to the next step.
2. Read the matching computational contracts in the ontological kernel; do not
   reread the extended corpus unless a derivation is genuinely ambiguous.
3. Run `python -m pytest diamond/tests -q` from the repository root, or
   `python -m pytest -q` from inside `diamond/`.
4. Make one bounded vertical change and add adversarial tests before connecting
   external state.
5. Run `python -m pytest -q`.
6. Update this file and `diamond/docs/WORKLOG.md` with actual behavior and
   limitations.
7. Do not touch Git or production `data/` without Tiago's explicit request.

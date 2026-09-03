# Fresta Diamond Architecture

Status: executable architectural draft — milestones 1–3 implemented  
Version: 0.2.0-draft  
Authority: subordinate to [`../ONTOLOGICAL_KERNEL-v3-DRAFT.md`](../ONTOLOGICAL_KERNEL-v3-DRAFT.md)

Current implementation and resumption map: `STATUS.md`.

## 1. Purpose

The Diamond is a clean, modular Fresta runtime extracted from behavior proven
in the Frankenstein implementation. It is not a rewrite of every existing
file. It contains only contracts and behavior that can be stated independently
of the REPL, Web UI, local data, a particular LLM, or a particular module.

The architecture must allow a third party to add a module without editing the
kernel, controller, blueprint, command registry, or user interface.

The Diamond initially has no user interface and no production data. Its first
surface is a deterministic test harness.

## 2. Ontological derivation

Every execution begins from a bounded objective. Relative to that objective:

- O1 identifies required concrete manifestations and observable results;
- O2 states explicit dependencies and witnesses between manifestations;
- O3 states contextual constraints, admissibility, provenance, effects, and
  completion boundaries;
- FILTER applies those constraints while preserving admitted and excluded
  alternatives;
- a typed remainder records a finite unresolved dependency or denial;
- PHI names only irreducible constitutional incompleteness. It is not the name
  of every missing input, capability, permission, or item of evidence.

The architecture therefore follows:

```text
objective
  -> mandatory constitutional firewall attestation
  -> blueprint requirements
  -> registered capability candidates       (weak O2 nomination)
  -> derived dependency plan
  -> structural validation and optional constitutional-depth validation
  -> authorized execution
  -> observed outputs and excluded costs
  -> completion, checkpoint, failure, or explicit typed remainder
```

Neither a module nor an operation has an intrinsic Three-Order rank. The
controller derives contextual roles for one plan. A role recorded in one scope
does not become a universal property of the component.

## 3. Constitutional invariants

1. The kernel is not a plugin and cannot be replaced by module registration.
2. The controller coordinates contracts; it contains no module-specific logic.
3. A blueprint declares an outcome, not a fixed sequence of implementation
   names.
4. Registry membership proves availability, not applicability or truth.
5. Semantic similarity nominates candidates but cannot close a plan.
6. Every executed operation must have typed inputs, typed outputs, declared
   effects, granted permissions, and a bounded failure contract.
7. Modules do not call one another directly. They exchange typed artifacts
   through a validated plan and runtime.
8. Persistent effects pass through effect brokers and domain gatekeepers.
9. LLM output is a proposal until parsed, scoped, and validated.
10. Technical success, structural closure, epistemic closure, and operational
    convergence are separate states.
11. Budget exhaustion produces a checkpoint or pause, never a PHI fixed point.
12. Missing capability, evidence, permission, or dependency remains an explicit
    typed remainder. The controller may not relabel a finite gap as PHI.
13. An excluded alternative or execution cost remains auditable as PHI-.
14. A completed bounded objective may stop while constitutional PHI remains.
15. Historical plans, decisions, effects, and revisions are append-only
    provenance. Correction creates a new version or transition.
16. Every controller-recognized analysis requires a valid constitutional
    firewall attestation. Model or module output without it remains a proposal,
    not an authorized Fresta analysis.

## 4. Architectural layers and authority

### 4.1 Ontological kernel

The kernel owns only invariant validation:

- contextual Three-Order closure;
- FILTER/PHI grounding;
- distinction between nomination and constitutive witness;
- closure-state vocabulary;
- provenance and revision invariants;
- constitutional rejection reasons.

Ordinary post-differentiation analysis does not need to traverse constitutional
PHI/F explicitly. The blueprint selects `CONTEXTUAL` or `CONSTITUTIONAL`
analysis depth. Constitutional invariants remain authoritative in both cases,
but explicit grounding is evaluated only when requested by the bounded object.

It does not discover modules, choose providers, make network requests, execute
effects, or contain prompts for a specific model.

### 4.2 Module registry

The registry discovers candidates, derives minimum anti-entropy admission, and
indexes admitted manifests. It answers questions
such as:

- which operations provide a capability;
- which artifact schemas they consume and produce;
- which effects and permissions they request;
- which versions and kernel contracts they support;
- whether they are enabled for the current installation.

The registry never invokes a handler and never assigns O1/O2/O3. Candidate
compatibility is not self-declared: the trusted loader supplies origin evidence,
and `ModuleAdmissionPolicy` produces an immutable admitted/rejected report.

### 4.3 Blueprint resolver

The resolver receives a blueprint, bounded objective, available artifacts,
module catalog, and execution policy. It nominates operations, binds artifacts,
and constructs a dependency DAG.

Exact capability and schema compatibility are evaluated before semantic
matching. Semantic heuristics or an LLM may rank otherwise valid alternatives;
they may not make an incompatible operation executable.

### 4.4 Plan validator

The validator rejects a plan unless:

- every required input is external or produced by an earlier node;
- every required outcome is represented;
- all schemas and capability versions are compatible;
- all effects are declared and permitted;
- no hidden or unbounded cycle exists;
- required O1, O2, and O3 obligations have non-empty support;
- constitutive dependency edges include forward effect, return witness, and
  excluded alternative/cost where structural closure is claimed;
- completion conditions can be evaluated from produced artifacts;
- unresolved requirements are represented as typed remainders.

Validation does not execute operations.

### 4.5 Effect broker and authorization

All external or persistent effects are mediated by capability-specific brokers,
for example:

- memory proposals and promotion;
- filesystem read/write;
- network read;
- process execution;
- configuration mutation;
- module installation;
- user-visible or third-party communication.

A manifest declaration is a request, not authorization. Execution receives a
short-lived capability grant scoped to the plan, operation, resources, and
budget. The handler cannot expand that grant.

### 4.6 Runtime

The runtime executes only validated and authorized plans. It owns:

- dependency scheduling;
- artifact delivery;
- effect grants;
- checkpoints and resumption;
- retries allowed by policy;
- time, token, and resource budgets;
- event emission;
- cancellation and sleep;
- final operational-state calculation.

Independent nodes may run concurrently. Nodes with shared effects or explicit
dependencies remain ordered. The initial prototype may execute sequentially
while preserving the same DAG contract.

#### Future snapshot-based multi-provider execution (WIP)

Parallel execution must not mean several providers mutating one live attention
context. Before fan-out, the kernel seals an immutable `WorkspaceSnapshot`
manifest referencing the exact attention revision, objective, sheets, artifacts,
remainders, plan frontier, authority labels, and content hashes visible to the
workers. A snapshot is a detailed index over existing immutable objects, not a
copy of the entire memory.

Every worker receives the same snapshot ref or an explicitly derived child
snapshot and writes only to its own revisioned sheet/artifact namespace. Its
reply names the exact input snapshot and target sheet revision. Workers may run
concurrently, but persistent memory and foreground attention remain single-writer.

At fan-in, the controller compares each worker's input snapshot with the current
head. An unchanged result may proceed to normal validation. A stale result is
never silently committed: dependency differences determine whether it can be
revalidated/rebased, must be rerun, or should remain archived as historical work.
The model may advise this decision, but cannot change snapshot identity or source
authority.

Snapshots should be sealed at semantic boundaries (before fan-out, after a
commit, on sleep/checkpoint, and before external effects), with optional timed
snapshots for long sandbox work. Time alone is not the correctness boundary;
the exact revision/hash relation is.

An objective-relative O3 analysis may also emit a typed `SNAPSHOT_REQUIRED`
proposal when it detects that the admissibility boundary, governing constraints,
authority relation, unresolved remainder set, or intended branch would make the
current state unsafe to treat as one continuous working surface. The controller
validates that proposal and seals the current head; the model cannot invent a
revision, backdate a snapshot, or grant it authority. O3 is therefore a semantic
snapshot trigger, while the kernel remains the only snapshot writer.

Provider topology remains configurable without changing blueprints:

- `SINGLE_CORE`: one model provides all admitted LLM capabilities sequentially;
- `MULTI_CORE_SEQUENTIAL`: a stable primary model plus bounded specialist
  providers, still executed one at a time;
- `MULTI_CORE_PARALLEL`: independent workers fan out over one sealed snapshot,
  followed by validated fan-in and one foreground commit.

This section records a future concurrency contract. The current Diamond runtime
remains sequential and must not simulate parallelism by sharing mutable state.

### 4.7 Controller

The controller is a small façade over registry, resolver, validator,
authorization, and runtime. It owns the state transition between phases but no
provider-specific behavior.

The controller is dependency-injected and replaceable. It is not a global
singleton and is not itself a permanent Order-3 module.

After technical execution, the controller may pass typed kernel-evidence
artifacts to the injected ontology evaluator. This post-execution phase updates
only structural and constitutional closure. It does not rewrite technical
completion, operational convergence, or epistemic state.

The controller then passes typed claim-evidence artifacts to the independent
epistemic evaluator. When an `EventJournal` is injected, the controller also
records phase transitions and returns only the events appended by that request.
It does not own event persistence or mutate previous events.

### 4.8 Workspace and memory

A task workspace stores provisional artifacts, plans, checkpoints, drafts,
attention state, raw provider replies, validation reports, and PHI. It is not
long-term memory.

The first implemented workspace primitive is an optional in-memory
`EventJournal`. It records deeply immutable snapshots with monotonic sequence,
correlation, subject, and causal parent. Large or sensitive payloads remain in
referenced artifacts; effect arguments and provider contents are not copied
into journal metadata.

An injected `JsonlJournalArchive` may seal the events of one controller request
as a persistent segment. Importing or running Diamond without that explicit
dependency creates no archive directory and performs no filesystem write.

The first resumable runtime contract adds an explicit per-episode operation
budget and an immutable in-memory checkpoint. The checkpoint preserves the
validated plan, completed and pending node frontier, external/intermediate
artifacts, public outputs, active remainders, prior checkpoint ID, and the hash
of the archived journal segment when available.

Persistent memory accepts only proposals through its own lifecycle and
Three-Order gate. A module cannot write a confirmed card or concept directly.

The cognitive workspace now stores append-only `SheetRevision` records with
typed elements and derived backlinks. Selecting elements creates only an
`UNVALIDATED_WORKSPACE_PROPOSAL`. The prefabricated
`workspace.learn-proposal` blueprint resolves `learn.prepare-proposal@1`
through the normal registry/controller path and emits a typed learning
proposal. Technical completion of this intake does not set structural,
constitutional, or epistemic closure.

The first evaluation slice makes one bounded LLM call for a coherent bundle:
structural evidence plus epistemic mode assessments. A deterministic fan-out
then emits the two canonical evidence artifacts, and the existing independent
validators retain verdict authority. Additional model calls are sequential,
remainder-guided repairs rather than parallel reinterpretations. Epistemic
closure for `ATTESTATION` means that a source report is represented correctly;
it does not upgrade the reported content to empirical truth.

`CrystallizationGate` consumes the original learning proposal and both
validator reports. It derives one state per selected element:

- `PROVISIONAL` for burden-satisfied attestations, hypotheses, and forecasts;
- `DEFERRED` for resolvable missing structure or evidence;
- `QUARANTINED` for contradiction, scope/policy failure, or trusted-boundary
  mismatch;
- `ACCEPTED` only for stronger modes whose own burden is satisfied.

There is deliberately no `CONFIRMED` crystal state. `PHI_MINUS` is reserved for
a future explicit negative-boundary decision, not generic rejection. The
isolated JSONL crystal store invokes the gate itself and preserves immutable
candidate lineage; it is not connected to production memory.

### 4.9 Interface adapters

Web, REPL, API, scheduled maintenance, and future agent surfaces are adapters
over the same objective and blueprint contracts. They may:

- parse surface-specific input;
- select or request a blueprint;
- provide external input artifacts;
- stream runtime events;
- render the final closure report.

They contain no domain operation chain and never import a provider module.
Slash commands are optional aliases for blueprint objectives, not a second
execution architecture. A capability added by a community module becomes
available to every interface through registry/controller discovery without
surface-specific registration.

The first implemented adapter-neutral boundary is `DiamondCommandService`.
`CommandRegistry` resolves canonical names and aliases; handlers translate only
into public `DiamondApplication` operations and may not duplicate a cognitive
pipeline. REPL and Web consume the same `CommandResult` JSON codec. Command
authority records invocation/result provenance only and cannot validate model
content or bypass a domain Gatekeeper. Community commands may add a surface
alias for a capability, but the underlying capability remains discoverable and
executable independently of that alias.

## 5. Core contracts

The language below is illustrative. Concrete serialization may be JSON, Python
types, or another schema language, provided the semantics are preserved.

### 5.1 ModuleManifest

```yaml
module_id: community.wikipedia-source
version: 1.0.0
kernel_contract: ">=3.0,<4.0"
sdk_contract: ">=1.0,<2.0"
trust_state: DISCOVERED
operations:
  - wikipedia.search
metadata:
  publisher: example
  license: example
```

Required module lifecycle:

```text
DISCOVERED -> QUARANTINED -> VERIFIED -> ENABLED
                                  |          |
                                  v          v
                               REJECTED   DISABLED
```

Discovery never implies enablement. The implemented verification validates
manifest structure, trusted-loader provenance/digest policy, protected
capabilities, effects, permissions, and effectful-community declaration
burdens. Signature/publisher verification and isolated code inspection remain
future loader responsibilities.
Manifest discovery occurs before provider code is loaded. Unverified module
code is not imported merely to learn what permissions it requests.

### 5.2 OperationContract

```yaml
operation_id: wikipedia.search
version: 1.0.0
capabilities:
  - source.search@1
  - concept.vocabulary_discovery@1
inputs:
  query: artifact://search-query@1
outputs:
  source_units: artifact://source-unit-list@1
effects:
  - network.read
permissions:
  - network.host:wikipedia.org
preconditions:
  - query.is_bounded
postconditions:
  - every_source_unit_has_provenance
failure_modes:
  - TIMEOUT
  - NO_RESULTS
  - MALFORMED_SOURCE
cost_model:
  external_requests: 1
determinism: EXTERNAL
idempotency: SAFE_RETRY
```

An operation is the smallest independently executable unit. A module may
provide many operations. Operation identity and version are stable; display
labels are not identifiers.

Handlers receive immutable input artifacts and an execution context containing
only granted ports. They return artifacts and events. They do not mutate a
shared state dictionary.

### 5.3 Capability

A capability is a namespaced, versioned semantic contract, not free-form prose:

```text
source.search@1
source.read@1
memory.retrieve@1
memory.propose@1
concept.compare@1
concept.recognition_plan@1
three_orders.validate@1
workspace.checkpoint@1
```

Human descriptions and aliases may help discovery. Exact IDs, versions, and
artifact schemas determine technical compatibility.

### 5.4 Artifact

```yaml
artifact_id: uuid
schema: artifact://source-unit@1
producer:
  plan_id: uuid
  operation_id: wikipedia.search
  execution_id: uuid
created_at: timestamp
scope:
  objective_id: uuid
payload: {}
provenance:
  inputs: []
  sources: []
integrity:
  content_hash: sha256
```

Artifacts are immutable. Correction produces a new artifact linked by a
revision or invalidation event. Large payloads may be stored externally and
referenced by content-addressed handles.

### 5.5 Blueprint

```yaml
blueprint_id: research_concept
version: 1
status: BUILTIN | DRAFT | CONFIRMED | DISABLED
intent: Verify recognition and local applicability of a concept.
inputs:
  - artifact://concept-candidate@1
orders:
  O1:
    requires:
      - capability: concept.recognition_plan@1
      - capability: source.search@1
    produces:
      - artifact://source-unit-list@1
  O2:
    requires:
      - capability: concept.compare@1
    produces:
      - artifact://concept-comparison@1
  O3:
    requires:
      - capability: three_orders.validate@1
    produces:
      - artifact://concept-validation@1
constraints:
  - external appearance is attestation, not truth
  - characteristic-first search precedes preferred-label search
completion:
  - recognition state evaluated
  - local fit evaluated
  - counterevidence preserved
budgets:
  external_requests: 8
  llm_tokens: 20000
effect_policy:
  allowed:
    - network.read
    - workspace.write
  confirmation_required:
    - memory.promote
```

A blueprint may name capability contracts and artifact outcomes. It may not
name a provider or prescribe a fixed implementation chain. A provider-specific
blueprint is permitted only when provider choice is itself part of the bounded
objective.

### 5.6 ExecutionPlan

```yaml
plan_id: uuid
objective_id: uuid
blueprint_id: research_concept
blueprint_version: 1
nodes: []
edges: []
contextual_roles:
  O1: []
  O2: []
  O3: []
external_inputs: []
required_permissions: []
estimated_cost: {}
completion_checks: []
remainders: []
validation_state: PROPOSED
```

Each node binds one operation version to concrete input and output artifact
schemas. Each edge states why an output satisfies a consumer input. A plan may
contain a bounded sub-blueprint node. Recursion must declare its objective,
budget, checkpoint boundary, and stopping condition.

### 5.7 Remainder

The first executable slice used the provisional Python name `PhiRemainder`.
That name must be migrated before the contract is persisted: only
`CONSTITUTIONAL_REMAINDER` denotes PHI; all other kinds are finite operational,
technical, evidential, or authorization remainders.

```yaml
remainder_id: uuid
kind: MISSING_CAPABILITY | MISSING_INPUT | MISSING_EVIDENCE |
      PERMISSION_DENIED | CONTRADICTION | BUDGET_EXHAUSTED |
      EXTERNAL_UNCERTAINTY | INVALID_DIRECTION | INVALID_SCOPE |
      UNUSED_EVIDENCE | CONSTITUTIONAL_REMAINDER
object_ref: artifact-or-plan-reference
description: bounded human-readable statement
required_for: plan-node-or-completion-check
resolvable: true | false | unknown
suggested_capability: optional
created_by: validator-or-operation
status: OPEN | ACCEPTED | RESOLVED | SUPERSEDED
```

`BUDGET_EXHAUSTED` is operational incompleteness and never a constitutional
fixed point. Resolution appends a transition and evidence; it does not erase
the original remainder.

### 5.8 StructuralEvidenceGraph

The executable ontological boundary receives immutable records for:

- bounded O1 manifestations with provenance;
- strong-O2 relations with forward justification, constraint effect, return
  witness, scope, and excluded cost;
- contextual O3 constraints;
- FILTER selections joining O1, O3, and the excluded complement;
- optional constitutional grounding with the explicit computational directions
  `OPENNESS -> FILTER -> OBJECT` and `OBJECT -> FILTER -> OPENNESS`.

The first implementation lives in `src/fresta_diamond/ontology.py`.
`OntologicalValidator` derives reciprocal, constitutional, and structural
verdicts without consulting a model closure checkbox. It rejects missing or
unused evidence, empty witnesses, scope mismatch, absent costs, discontinuous
filters, and reversed directions.

Providers emit this contract as
`artifact://structural-evidence-graph@1`. The runtime creates the immutable
artifact and the controller delegates decoding and validation to
`OntologyEvaluator`. No provider passes an out-of-band closure verdict to the
controller. Malformed payloads remain visible remainders; valid and invalid
reports are both attached to the observable controller result.

This validates structural form and constitutional direction. Non-empty natural
language is not automatically true: semantic claims still require parsed,
auditable evidence and the appropriate epistemic burden.

At `CONTEXTUAL` depth, a reciprocal local graph may set
`structural_closed=true` while `constitutional_closed=null`. At
`CONSTITUTIONAL` depth, or whenever grounding evidence is supplied, the fixed
directions are validated explicitly. Constitutional failure does not silently
erase an independently valid local structure.

The dependency is asymmetric: local structural closure does not require
constitutional evaluation, but `constitutional_closed=true` does require a
valid local structure through which the grounding path reaches its object.

### 5.9 EpistemicEvidenceGraph

Semantic support is carried separately from the structural Three-Order witness
as `artifact://epistemic-evidence-graph@1`. The first implementation lives in
`src/fresta_diamond/epistemology.py`.

Each claim declares one burden-bearing mode:

- `OBSERVATION`;
- `ATTESTATION`;
- `DERIVATION`;
- `HYPOTHESIS`;
- `FORECAST`;
- `INVARIANT`.

Evidence events preserve stance, kind, source actor, exact source locator,
source lineage, context, method, observation time, and scope. Source actor,
claim subject, and memory owner remain separate references. A document reporting
an identity statement can therefore satisfy an attestation burden without
becoming a direct observation of the user.

`EpistemicValidator` applies deterministic minimum burdens by mode. For example,
an observation needs an observation event; a derivation needs premises,
constraints, direction, and premise evidence; a hypothesis needs a bounded test;
a forecast needs a horizon and assumptions; and an invariant needs explicit
counterexample search plus independent supporting lineages. Repeated copies of
one lineage do not count as independent support. Live counterevidence prevents
closure in the same bounded claim graph.

`EpistemicEvaluator` updates only `epistemic_closed`. Structural and
constitutional axes remain untouched and may stay `None`. A satisfied
hypothesis burden means that the claim is properly represented as a testable
hypothesis; it does not silently relabel it as a confirmed observation.

This first cut validates evidence contracts only. It does not yet persist
claims, calculate confidence, assign card lifecycle state, resolve overlapping
scopes, or promote anything into memory.

### 5.10 ClosureReport

Every plan, analysis, and final execution report names the distinct closure
axes defined by the ontological kernel:

```yaml
report_id: uuid
object_ref: objective-or-artifact-reference
scope: {}
criterion: bounded statement
technical_completed: true | false
constitutional_closed: true | false | not_evaluated
structural_closed: true | false
operational_converged: true | false
epistemic_closed: true | false | not_applicable
historical_resolved: []
active_remainders: []
stopping_reason: OBJECTIVE_SATISFIED | EXPLICIT_RULE | PAUSED_FOR_SLEEP |
                 BUDGET_EXHAUSTED | CANCELLED | FAILED | OPEN
supporting_artifacts: []
validation_reports: []
```

The axes vary independently. In particular:

- an operation may complete technically while its output fails validation;
- a plan may be structurally closed while produced claims remain epistemically
  deferred;
- an objective may be satisfied while constitutional PHI remains;
- budget exhaustion pauses open work and does not set
  `operational_converged=true` unless the blueprint explicitly defines that
  bounded budget result as its objective;
- an LLM-provided `closed` or `converged` value is advisory evidence, never the
  report verdict.

### 5.11 Execution state

Execution uses an explicit state machine rather than a boolean result:

```text
PROPOSED -> VALIDATED -> AUTHORIZED -> RUNNING
    |           |            |           |
    v           v            v           v
 REJECTED    REJECTED      DENIED      COMPLETED
                                        PAUSED
                                        OPEN
                                        FAILED
                                        CANCELLED
```

`COMPLETED` means the runtime finished the validated plan. The accompanying
`ClosureReport` states what that completion establishes and what remains open.

### 5.12 JournalEvent

`src/fresta_diamond/journal.py` implements an in-memory append-only stream:

```yaml
event_id: uuid
sequence: positive-monotonic-integer
kind: typed-event-kind
correlation_id: plan-id
subject_ref: plan-node-effect-or-validator-reference
causation_id: prior-event-id | null
recorded_at: utc-timestamp
payload: deeply-immutable-metadata
```

The journal assigns IDs, sequence, and time; callers cannot provide or rewrite
them. A causal parent must already exist in the same journal. Queries return
tuples of frozen event snapshots. One shared journal may contain several plans,
while each controller result exposes only the events appended during its call.

This is audit infrastructure, not truth memory. It records that a validation or
effect occurred; the corresponding validator, grant, artifact, and report
determine what the event means.

`JsonlJournalArchive` stores one canonical JSON segment per line using
`fresta://journal-segment@1`. Each segment contains only one correlation ID,
requires contiguous event sequences, includes the prior segment hash, and is
sealed by SHA-256 over its canonical body. Reads revalidate the complete chain
and reject modified or malformed history.

The archive is inactive historical memory: callers query segments explicitly
by correlation rather than injecting the full archive into attention. This
first implementation is single-process and reads the file for verification; it
is not yet a concurrent database or high-volume index.

When archive persistence is configured but fails after technical execution, the
produced artifacts remain visible and are not automatically repeated. The
controller sets `operational_converged=false`, adds an
`EXTERNAL_UNCERTAINTY` remainder, and emits `JOURNAL_ARCHIVE_FAILED` in the
volatile journal.

### 5.13 ExecutionBudget and RuntimeCheckpoint

`ExecutionBudget(max_operations=N)` is the first concrete biological clock. It
counts completed operations in one active episode. `None` is explicitly
unbounded; zero pauses before the first pending node.

Before starting a node, the runtime checks the remaining budget. Exhaustion
produces:

- `ExecutionState.PAUSED`;
- `operational_converged=false`;
- `stopping_reason=BUDGET_EXHAUSTED`;
- a typed `BUDGET_EXHAUSTED` remainder;
- `CHECKPOINT_CREATED` and `EXECUTION_PAUSED` events;
- an immutable `RuntimeCheckpoint`.

`DiamondController.resume()` requires a fresh budget, revalidates the stored
plan against the current registry, obtains new authorization, emits
`EXECUTION_RESUMED`, and supplies the preserved artifact frontier to the
runtime. Completed nodes are skipped. A missing or changed provider leaves the
objective open rather than replaying completed work or selecting an unrelated
fallback.

When an archive is configured, the returned checkpoint records the sealed
segment hash. Resume refers to that hash in the next segment, connecting active
state with archived history.

This first budget measures operation count only. `JsonCheckpointStore` can
persist the checkpoint and all provisional artifact payloads under
`fresta://runtime-checkpoint@1`. Each checkpoint ID maps to one immutable JSON
record sealed by SHA-256; saving the same ID twice or loading modified content
is rejected.

Checkpoint persistence requires an injected journal archive so the stored
frontier contains the hash of the historical segment that produced it. A new
process may create fresh controller, journal, archive, and store instances,
load the checkpoint, revalidate the plan, and resume.

No directory is created until a store is explicitly injected and a pause is
actually persisted. This is an isolated provisional workspace, not the
production memory store. Token, time, energy, and storage budgets will extend
the same contract.

If checkpoint persistence fails, the in-memory frontier and technical outputs
remain visible, while `operational_converged=false`,
`CHECKPOINT_PERSISTENCE_FAILED`, and an `EXTERNAL_UNCERTAINTY` remainder expose
that sleep is not yet durable.

## 6. Resolution algorithm

The default resolver follows a bounded deterministic-first procedure:

1. Validate the blueprint and objective schemas.
2. Expand required capability and artifact obligations.
3. Query the registry for exact compatible operations.
4. Reject candidates with incompatible schemas, versions, effects, permissions,
   trust states, or policies.
5. Rank remaining candidates by explicit capability fit, local availability,
   cost, reliability, and prior scoped execution evidence.
6. Use semantic heuristics only to nominate mappings not expressed by exact
   contracts.
7. Ask an LLM only when a bounded ambiguity or missing semantic mapping remains.
8. Build the smallest dependency DAG satisfying the declared outcome.
9. Record contextual O1/O2/O3 roles for this plan.
10. Run structural, dataflow, and authorization validation; run explicit
    constitutional grounding only when required by the objective depth.
11. Return a validated plan or explicit typed remainders. Never silently fall
    back to an unrelated implementation or rename a finite gap as PHI.

Plan choice may be stochastic; plan validity is not delegated to a model.

## 7. Execution and observation

The runtime emits append-only events:

```text
PLAN_PROPOSED
PLAN_VALIDATED | PLAN_REJECTED
AUTHORIZATION_GRANTED | AUTHORIZATION_DENIED
OPERATION_STARTED
OPERATION_OUTPUT
OPERATION_FAILED
EFFECT_REQUESTED
EFFECT_COMMITTED | EFFECT_REJECTED
ONTOLOGY_EVALUATED
EPISTEMIC_EVALUATED
CHECKPOINT_CREATED
EXECUTION_PAUSED | EXECUTION_RESUMED
OBJECTIVE_COMPLETED | OBJECTIVE_OPEN | EXECUTION_FAILED
```

An operation result contains:

- produced artifacts;
- observations supporting postconditions;
- requested effects and their outcomes;
- excluded alternatives or costs;
- new typed remainders;
- measured resource usage.

The runtime validates outputs against schemas and postconditions before making
them available downstream. A handler's `success=true` is never sufficient.

The current implementation emits plan, authorization, operation, effect,
ontology, epistemic, checkpoint, pause, resume, and final-objective events.

## 8. LLM boundary

All runtime material reaches `llm.generate` through a host-owned inert-data
contract. Only the first system message may contain instructions; subsequent
messages contain typed JSON data with no instruction authority. The effect
boundary rejects unframed material before invoking an adapter. Host decoders
continue to restore identity, scope and allow-lists because prompt separation
does not make model output authoritative or true.

An LLM may:

- interpret a user objective;
- fill a typed blueprint input;
- rank technically compatible candidates;
- propose a semantic capability mapping;
- generate queries, comparisons, or drafts;
- decide among permitted strategies;
- propose subobjectives or blueprints;
- summarize execution for the user.

An LLM may not:

- register or enable a module;
- fabricate a capability or artifact;
- bypass a schema, permission, gatekeeper, or validator;
- directly commit a persistent effect;
- treat its own convergence claim as kernel closure;
- reinterpret budget exhaustion as PHI;
- change executable code through an ordinary blueprint.

Raw and parsed provider responses remain auditable workspace artifacts.

The first bounded implementation uses an OpenAI-compatible adapter behind the
`llm.generate` effect. Host, model, timeout, token ceiling, object, scope, and
analysis depth are outside model authority. `LlmEvidenceOperation` converts the
response into a proposal for `artifact://structural-evidence-graph@1`; the
ordinary decoder and ontology evaluator remain the only closure path.

Constitutional prompts include the compact kernel meaning of OPENNESS and
FILTER. Providers may not substitute epistemic ignorance, named external
theories, or invented observations for constitutional grounding. Nested scopes
and provenance remain validator-visible rather than being silently repaired.

## 9. Community extension contract

A community module is acceptable only when it ships:

1. a valid manifest;
2. versioned operation and artifact contracts;
3. declared effects, permissions, costs, and failure modes;
4. conformance tests using fake ports;
5. deterministic fixtures for parsing and schema validation;
6. provenance for generated source units;
7. no import-time effects;
8. no direct access to memory or another module;
9. compatibility bounds for kernel and SDK versions;
10. an uninstall/disable path that preserves historical execution provenance.

The loader discovers modules through an SDK entry-point mechanism or configured
module directory. The default registry contains no hardcoded imports of
community packages.

Community blueprints are data. They begin as `DRAFT`, may be analyzed and
tested, and require `CONFIRMED` status before persistent effects. A blueprint
cannot make an untrusted module trusted.

## 10. Failure, retry, sleep, and recursion

- Retries are allowed only for declared retry-safe failures and remain bounded.
- A non-idempotent effect is never repeated without an idempotency key or
  explicit reconciliation.
- Missing inputs pause or reject the dependent node; they do not become empty
  values.
- Budget thresholds create checkpoints containing active objective, frontier,
  artifacts, plan version, unresolved remainders, and resumable operation state.
- Sleep is a resource transition, not epistemic closure.
- A module needing another capability returns a typed subobjective or remainder
  to the controller. It never locates and calls another module itself.
- Recursive blueprints reuse O1/O2/O3 relative to the new bounded object. They
  do not create O4 or an unbounded execution loop.

## 11. Frankenstein compatibility boundary

The Frankenstein remains an executable research lab and behavioral oracle. It
is not imported as the Diamond core.

Compatibility is provided through explicit adapters:

- legacy card/topic JSON reader;
- local OpenAI-compatible LLM adapter;
- Frankenstein experiment-profile fixtures;
- optional command-surface adapter after the core is stable.

No Diamond domain object contains a `legacy` field solely to preserve an old
implementation detail. Compatibility metadata stays in adapters or provenance.

### Succession contract

Diamond is not a permanent companion process or plugin for Frankenstein. It is
the successor implementation intended to become the primary Fresta Protocol.
Its runtime, stores, configuration, providers, command service, and future
interfaces must operate when the Diamond directory is moved to an independent
repository with no Frankenstein package or data tree available.

The Frankenstein may supply behavioral observations and migration inputs only
through optional boundary adapters. A feature does not count as migrated while
Diamond needs a Frankenstein import, process, path, configuration value, or
mutable data store to execute it. Cross-benchmarks prove comparison, not runtime
dependency.

When the required capabilities reach acceptance, promotion means renaming the
standalone Diamond distribution to Fresta Protocol; it does not mean embedding
Diamond inside the old implementation.

## 12. First prototype acceptance test

The first Diamond milestone contains:

- kernel contracts and validators;
- an in-memory artifact/workspace store;
- module manifest loader;
- registry;
- deterministic resolver;
- plan validator;
- sequential runtime;
- fake effect broker;
- one minimal blueprint;
- two interchangeable test modules providing the same capability.

Acceptance scenario:

1. Register provider A and derive a valid plan.
2. Execute the plan and validate its artifacts.
3. Disable provider A and register provider B without editing the controller or
   blueprint.
4. Derive and execute an equivalent valid plan.
5. Register an incompatible or unauthorized provider and prove deterministic
   rejection with explicit typed remainders.
6. Remove a required provider and prove the objective remains open without a
   fabricated fallback.
7. Verify that neither provider can write persistent memory directly.

The architecture is not modular merely because files are separated. This
provider-substitution test is the minimum proof that contracts, rather than
hardcoded module knowledge, govern execution.

## 13. Autonomous module-design boundary

Autonomy begins with a typed gap, not with unrestricted code generation. A
missing-capability remainder is compared with the current operation inventory.
An exact provider causes deterministic reuse; otherwise the model may return
`NO_NEW_MODULE` or one O1/O2/O3 operation design below the controller.

The host anchors capability, schemas, layer, effects and permissions. Model
effects/permissions must be subsets of the host boundary, empty by default.
The anti-entropy check over a design is only a preflight: the result remains
`UNVALIDATED_MODULE_DESIGN` and cannot create, install, admit or enable code.
Every decision is stored immutably, including rejected proposals, so future
Φ− aggregation can learn from repeated failure without silently rewriting
history. See [System design](DESIGN.md).

## 14. Deferred decisions

The following choices remain implementation details until benchmarked:

- Python entry points versus a configured module directory;
- in-process handlers versus subprocess/RPC isolation;
- JSON Schema versus typed Python plus serialized schema descriptors;
- persistent event database versus append-only files;
- resolver optimization strategy after exact compatibility filtering;
- package signatures and community trust infrastructure;
- concurrent scheduler implementation.

These decisions may change without changing the constitutional contracts above.

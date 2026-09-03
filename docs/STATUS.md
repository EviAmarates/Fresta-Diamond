# Fresta Diamond status

**Checkpoint:** 2026-09-03
**Maturity:** executable research prototype / public WIP preparation  
**Latest local verification:** 425 Diamond tests
**Last recorded cross-system baseline:** 527 combined tests with the original
prototype.

## What currently works

- Immutable contracts, module registration/admission, dependency resolution,
  plan validation, and sequential bounded execution.
- Constitutional firewall attestation, semantic prompt boundary, and an
  `EffectBroker` with explicit grants.
- Text-level learning through bounded LLM evidence, repair, Gatekeeper review,
  atomic learning-memory commits, and Phi-minus preservation.
- Native concepts: nomination, evidence, deterministic validation, bounded
  external research handoff, and versioned integration.
- Objective-relative retrieval over learning memory, concepts, sheets, and
  Phi-minus records.
- Multi-context attention memory, cognitive sheets, continuation checkpoints,
  bounded decomposition, sleep, and resume.
- Central command service, headless command runner, persistent REPL, and the
  first persistent chat path.
- Separate contracts/codecs and hash-lineaged stores for user-profile claims and
  assistant-personality traits. Public writes remain proposals; adoption is
  explicit and Gatekeeper-controlled.
- Shared objective-relative attention can resolve active profile and personality
  versions through separate namespaces; task-memory lifecycle does not delete
  those durable domains.
- Versioned meta/ontology memory stores convergent analyses and exposes them
  through the same attention resolver, preserving O1/O2/O3, FILTER, Phi-minus,
  remainders, and Phi openness.
- Kernel contracts classify provenance conservatively as internal, external,
  mixed, or unknown. Concept research queries carry typed pre-search intent,
  while source units retain source-document and extracted-unit lineage plus an
  explicit source lineage for independence accounting. Distinct URLs alone
  never establish independent support. Legacy provenance lists remain readable
  without granting authority.
- `AcademicLibrarySearchAdapter` now has mocked deterministic coverage for
  OpenAlex, Crossref, DOAJ, and Internet Archive, preserving unvalidated
  source-lineage metadata without authority or promotion.
- The benchmark layer now has a deterministic question-only contract that
  compares a persistent Fresta path against an isolated baseline with bounded
  episodes, injectable adapters, checkpointed continuation, and provenance-
  preserving unvalidated evidence. A reproducible local CLI runner now exists
  for one explicit question-only case; it does not claim live Web readiness.
- The kernel now names the existing Firewall/Gatekeeper/revalidation loop as
  the Lens and defines structural saturation as contextual loss of
  recoverability. The user-facing explanation is staged in
  [`ONTOLOGY-GUIDE.md`](ONTOLOGY-GUIDE.md).
- The persistent application facade now wires one append-only controller
  journal archive into its normal execution paths, so benchmark/application
  runs retain auditable plan, authorization, effect, validation, and stopping
  events.
- Firewall DENY now routes through a consultative escalation service that
  snapshots a runtime checkpoint, journals the escalation, and stores an open
  meta-analysis report in meta-memory. QUARANTINE remains review-only, and the
  controller hook keeps the remaining integration explicit instead of
  introducing parallel authority.
- The public documentation describes Fresta as a functionally second-order
  cybernetic hippocampal layer for LLMs: persistent, objective-relative memory
  and active-observation support, not a biological or consciousness claim.
- Meta-analysis reports now expose a structured Lens recoverability assessment:
  `UNASSESSED`, `RECOVERABLE`, `AT_RISK`, `RESIDUAL`, or `CONTESTED`.
  `RESIDUAL` requires an explicit structural witness and is never inferred from
  a score, timeout, or remainder count.

## Important limitations

- The Web surface is a minimal loopback-only HTTP adapter with a local UI and
  ephemeral transport token. Direct questions now run through the shared
  retrieval → research → `/learn` → attention path and expose source lineage,
  authority, remainders, and continuation state. There is no user
  authentication or production deployment profile.
- The same persistent chat turn can request `conversation` or `analysis`
  response mode. The mode frames presentation only; it does not alter
  authority, provenance, budgets, or Phi openness.
- Chat is persistent with conditional reflection, lifecycle handling and
  profile proposals; retention and encryption remain WIP.
- `/learn` supports bounded UTF-8 document intake, lossless decomposition,
  batching, durable checkpoints and resume; full convergence orchestration is
  still WIP. Meta-analysis exposes conservative saturation and revalidation
  diagnostics without treating either as closure.
- The historical benchmark currently has a deterministic curated replay case;
  the deterministic question-only runner contract now exists, plus a local CLI
  runner for one explicit case, but a live Web-enabled comparison still needs a
  generic HTTP adapter path.
- `DiamondApplication.research_objective()` and the `research` command expose a
  bounded, controller-mediated Web research episode whose unvalidated source
  units enter the ordinary `/learn` path. Model-driven query selection is a
  bounded controller operation; the live endpoint is usable for local smoke
  tests but remains a development adapter, not production Web.
- CORE and Perseus adapters remain deferred until a credential-free,
  non-scraping contract is defined.
- `/brain analyze` exists as a deterministic immutable inventory/diagnosis path.
  `/brain apply` does not exist and remains deliberately separate.
- External effects are brokered but not yet strongly isolated from hostile
  in-process Python. Community modules require signatures, subprocess/RPC
  isolation, revocation, and a mature installation policy.
- The firewall is an engineering boundary under active adversarial testing, not
  a claim of complete security or semantic truth verification.
- The runtime is single-process and sequential. It has no production retention,
  encryption, multiprocess locking, or general cancellation policy.
- Contextual structural closure and epistemic evidence burdens do not prove that
  arbitrary natural-language claims correspond to reality. Appropriate sources
  and external verification remain necessary.

## Next milestones

1. Complete document `/learn` convergence limits and interruption policy.
2. Wire the generic HTTP adapter path for the question-only benchmark runner
   without granting new authority, reusing the direct investigation contract.
3. Expand adversarial firewall and Phi-minus coverage, including source
   diversity, saturation, conflict and revalidation.
4. Expand the ontology guide alongside the runtime WIPs without duplicating
   constitutional authority.
5. Define Web authentication, deployment, and lifecycle policy before exposing
   the loopback adapter beyond local development.
6. Add retention, encryption, multiprocess locking and cancellation policy.
7. Isolate community modules through signatures, subprocess/RPC and revocation.
8. Build the project-scoped Workspace Agent only through the same controller,
   firewall, `EffectBroker`, journal and checkpoints.
9. Keep any future `/brain apply` separately authorized, simulated, journaled,
   versioned and reversible.

## Verification

From the `diamond/` directory:

```powershell
python -m pytest -q
python scripts/run_benchmark.py --all
python scripts/run_cross_benchmark.py --all
```

The second and third commands use recorded fixtures by default and do not call
an LLM. Read [Operations](OPERATIONS.md) before running live local-model
smokes.

Detailed Portuguese checkpoint notes are retained in
[`legacy/pt/STATUS.pt.md`](legacy/pt/STATUS.pt.md).

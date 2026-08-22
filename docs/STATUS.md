# Fresta Diamond status

**Checkpoint:** 2026-08-19  
**Maturity:** executable research prototype / public WIP preparation  
**Latest local verification:** 344 Diamond tests  
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
- Separate contracts/codecs for user-profile claims and assistant-personality
  traits. They remain proposals; persistent stores are not implemented yet.

## Important limitations

- There is no Diamond Web server, user authentication, or production deployment
  profile.
- Chat is persistent but incomplete: profile integration, conditional
  reflection, per-turn retrieval, archive/abandon lifecycle, retention, and
  encryption are still WIP.
- `/learn` currently accepts bounded text objects. File/document intake,
  batching, resume orchestration, and convergence are planned.
- `/brain analyze` and `/brain apply` do not yet exist in Diamond.
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

1. Add versioned profile/personality stores, Gatekeepers, inspection, and
   controlled adoption.
2. Complete chat continuity and conditional reflection without promoting chat
   text directly into memory.
3. Implement `/brain analyze` as deterministic inventory + bounded diagnosis +
   immutable report. Any `/brain apply` must be separately authorized,
   simulated, journaled, versioned, and reversible.
4. Add document `/learn` orchestration with source-file intake, batching,
   checkpointing, sleep, resume, and explicit convergence limits.
5. Expand adversarial firewall and Phi-minus coverage.
6. Publish a command/application/blueprint/effect/store/authority connection
   map; then add a thin Web adapter.
7. Build the project-scoped Workspace Agent only through the same controller,
   firewall, `EffectBroker`, journal, and checkpoints.

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

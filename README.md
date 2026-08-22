# Fresta Diamond

> **Experimental pre-release.** Diamond is the clean, modular successor
> runtime for the Fresta Protocol. It is usable for research and local
> evaluation, not yet a production system.

**Fresta Diamond is a Python runtime that validates typed LLM proposals,
persists state outside the context window, and mediates effects through explicit
grants.** The model may generate an interpretation or proposed action; Fresta
decides what may be validated, persisted, executed, deferred, or rejected.

Diamond rebuilds only the parts of the original Fresta prototype that can be
given independent contracts and deterministic tests. Its intended final name is
simply **Fresta Protocol**.

**Latest verification:** 344 Diamond tests passed on 2026-08-19. The last
recorded cross-system baseline passed 527 combined tests with the original
prototype.

## Run it now

Requirements: Python 3.10+. Deterministic tests do not call an LLM. Live runs
need an OpenAI-compatible local endpoint.

```powershell
cd C:\Users\User\fresta-novo\diamond
python -m pip install -e ".[dev]"
python -m pytest -q
python run_commands.py --data-root .\local-command-data --command "/help"
```

For a persistent local session:

```powershell
python run_repl.py --data-root .\local-repl-data
```

Every data root is explicit. Diamond never infers or opens the original
prototype's `data/` directory.

## What works today

- Typed contracts, module admission, dependency planning, validation, and
  bounded execution.
- Text `/learn` with atomic learning-memory commits, epistemic states, and
  Phi-minus preservation.
- Objective-relative retrieval, concepts, attention contexts, cognitive sheets,
  checkpoints, sleep, and resume.
- A shared command service, headless runner, persistent REPL, and the first
  persistent chat path.
- Constitutional firewall attestation and brokered effects with explicit grants.

The Web, Workspace Agent, document-scale learning, `/brain analyze`, profile
stores, and production hardening are not implemented yet. See
[Status](docs/STATUS.md) for the exact boundary.

## Why Fresta

LLMs are useful generators, but their context windows, output formats, and
confidence statements are not persistent memory or authority. Fresta provides
an external runtime for:

- bounded, objective-relative retrieval instead of dumping all history into a
  prompt;
- persistent, append-only memory with explicit epistemic states;
- contextual Three-Order analysis (`O1`, `O2`, `O3`) and structural witnesses;
- explicit distinction between candidates, evidence, active knowledge,
  quarantine, and unresolved remainders;
- attention contexts, cognitive sheets, checkpoints, sleep, and resume outside
  the model context window;
- controlled effects through narrow, revocable grants;
- immutable journals and auditable state transitions.

```text
LLM      = proposal, interpretation, bounded generation
Fresta   = memory, contracts, validation, permissions, execution, continuity
```

The LLM remains essential: it interprets ambiguous input and proposes useful
work. It does not get to validate its own output, silently promote memory, or
perform ungranted external effects.

## Detailed implementation status

Profile and assistant-personality contracts have focused coverage; their
persistent stores remain unfinished.

| Area | State |
|---|---|
| Contracts, controller, module registry, plan validation | Implemented |
| Constitutional firewall and effect broker | Implemented, hardening WIP |
| Text `/learn`, atomic learning commits, Phi-minus records | Implemented |
| Concepts, evidence, validation, bounded research handoff | Implemented |
| Attention contexts, cognitive sheets, checkpoint/resume | Implemented with bounded scope |
| Shared command service, command runner, persistent REPL | Implemented |
| Persistent chat spine | Implemented; reflection and profiles are WIP |
| User profile and assistant personality | Contracts implemented; stores are WIP |
| `/brain analyze` and document-scale learning | Planned |
| Web and Workspace Agent interfaces | Planned |

See [the current status](docs/STATUS.md) for limits and the next milestones.

## Architectural boundary

```text
bounded objective
  -> constitutional firewall attestation
  -> blueprint requirements and module candidates
  -> typed dependency plan
  -> plan validation
  -> effect authorization
  -> bounded execution
  -> structural / epistemic evaluation
  -> journal, outputs, checkpoint, or typed remainder
```

The runtime is designed around these rules:

1. A module is available only after admission; availability does not prove
   applicability or truth.
2. An LLM output is a proposal until parsing, scope checks, and validators have
   accepted it.
3. Retrieval is not confirmation, and a coherent answer is not automatically a
   verified fact.
4. Missing evidence, capability, permission, or time remains a finite typed
   remainder; it is never relabelled as `PHI`.
5. Every persistent effect goes through `EffectBroker` and an explicit grant.
6. History is append-only: correction creates a new version or transition.

The Three Orders are **relative to the bounded objective**. No memory card,
concept, module, or operation has a permanent O1/O2/O3 rank.

For the complete contract, read [Architecture](docs/ARCHITECTURE.md) and the
[system design guide](docs/DESIGN.md).

## Available command families

Useful examples include:

```text
/help
/learn A car converts energy into controlled motion.
/attention create Review the current learning state.
/workspace create Draft a bounded research note.
/chat start Discuss the current objective.
/chat say SESSION_ID What remains unresolved?
/concept list
/module suggest --output-schema JSON CAPABILITY OBJECTIVE
```

Command semantics, live-runner settings, and deterministic benchmark commands
are documented in [Operations](docs/OPERATIONS.md).

## Repository layout

```text
diamond/
├── src/fresta_diamond/   runtime package
├── tests/                deterministic and adversarial tests
├── testdata/             fixtures, baselines, and archived replay runs
├── scripts/              benchmarks and local-model smoke runners
├── docs/                 English canonical documentation
├── run_commands.py       one command through the shared service
├── run_repl.py           persistent REPL over the shared service
├── CONTRIBUTING.md       contribution and verification rules
└── SECURITY.md           security posture and disclosure guidance
```

`testdata/local-runtime/`, caches, build products, logs, and temporary local
data are ignored by Git. Fixtures and accepted baselines are intentionally kept
under version control.

## Documentation

- [Documentation index](docs/INDEX.md)
- [Architecture](docs/ARCHITECTURE.md)
- [System design](docs/DESIGN.md)
- [Operations](docs/OPERATIONS.md)
- [Current status and roadmap](docs/STATUS.md)
- [Security posture](docs/SECURITY.md)
- [Portuguese research archive](docs/legacy/pt/README.md)

The English documents above are canonical for the public runtime. Earlier
Portuguese design notes, worklogs, and operational drafts are preserved in the
archive for provenance. They are useful research history, not release
guarantees.

## Relationship to the original prototype

The original Fresta implementation is informally called **Frankenstein**. It is
the experimental laboratory where mechanisms were first discovered and tested.
Diamond is not a subpackage of it and must not require its imports, paths,
processes, configuration, mutable data, or interfaces.

When Diamond can run from a clean repository with its own stores, providers,
commands, interfaces, benchmarks, and migration tooling, it can be promoted and
renamed as the standalone **Fresta Protocol**. Frankenstein remains an archive,
regression laboratory, and optional migration source.

## Near-term roadmap

1. Add versioned stores, Gatekeepers, and inspection for user profiles and
   assistant-personality heuristics.
2. Complete per-turn chat retrieval, resume synchronization, and conditional
   reflection.
3. Implement `/brain analyze` as an immutable diagnostic/reporting path;
   applying changes remains separately authorized and reversible.
4. Add document-scale `/learn` with bounded batches, checkpoints, sleep, and
   explicit convergence criteria.
5. Publish a connection map, then build a thin Web adapter over the same command
   service.
6. Add an authorized Workspace Agent mode for project-scoped reads, patches,
   tests, diffs, and resumable work.

## Contributing and security

This is an early research prototype. Please read [CONTRIBUTING.md](CONTRIBUTING.md)
before proposing a change and [SECURITY.md](SECURITY.md) before reporting a
security issue. Do not place API keys, personal conversation data, or production
memory stores in the repository.

## License

MIT. See [LICENSE](LICENSE).

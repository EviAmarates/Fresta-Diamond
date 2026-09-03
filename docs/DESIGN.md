# Fresta Diamond system design

This document is a practical overview of the components that sit below the
architecture contract. It describes implemented behavior and intentionally
separates it from planned work.

## Ontological kernel and analysis depth

Diamond uses the Three Orders as a method relative to a bounded objective:

- **O1** — an observable manifestation or required result;
- **O2** — a relation, dependency, or witness between manifestations;
- **O3** — an admissibility constraint for the current scope.

An ordinary, post-differentiation analysis may close contextually through an
auditable O1/O2/O3 witness graph. A constitutional-depth analysis additionally
requires explicit grounding in `FILTER` and `PHI`.

`PHI` is not a generic unknown field. It names irreducible constitutional
incompleteness. Missing data, evidence, permissions, capabilities, or elapsed
budget are finite remainders and must remain typed as such.

The public derivation note is:

```text
PHI (openness / incompleteness)
  -> possibility of differentiation
  -> FILTER (coherent selection)
  -> differentiated objects
  -> relations, analyses, and structured worlds
```

`PHI` is treated as an axiom of the constitutional derivation. `FILTER` is a
derived requirement for coherent differentiation; it cannot exist outside
`PHI`. This is a constitutional closure, not a claim that all content in the
world is complete or known.

## Learning memory and epistemic state

`/learn` processes a bounded text object through workspace construction,
controller execution, bounded model evidence, repair where justified,
Gatekeeper review, and an atomic commit.

Learning memory retains distinct states. A candidate, a deferred record, a
quarantined record, and a confirmed crystal are not interchangeable. Retrieval
only selects relevant material; it does not validate or promote it.

Phi-minus records retain excluded alternatives, costs, and negative evidence so
that a later decision can be audited or reconsidered without rewriting history.

Document-scale `/learn` is not implemented yet. It will orchestrate bounded
batches, checkpoints, sleep, resume, and a stopping criterion over this same
pipeline rather than introducing a second learner.

## Concepts and external research

Concepts are versioned objects with signatures, memberships, aliases, parent
relationships, evidence, and validation state. They are not folders and do not
have intrinsic Three-Order ranks.

The current flow separates:

```text
committed crystals
  -> concept nomination
  -> candidate concept
  -> evidence proposal
  -> deterministic validation
  -> versioned integration or explicit gap
```

External concept research is a bounded evidence activity mediated by
`EffectBroker`. Source material has no automatic authority. It must return via
the ordinary learning and validation path before it can support a concept.

## Attention and cognitive workspace

Attention is a persistent, append-only working context outside the LLM window.
It has a foreground context, may be suspended/reactivated, may archive or be
marked abandoned, and projects only a budgeted subset into each model call.

Cognitive sheets preserve the working representation: revisions are immutable,
backlinks and hierarchy are hash-bound, and an active scratch sheet can contain
unvalidated work. A sheet is not learning memory. Promotion to durable knowledge
still requires `/learn` and the relevant Gatekeepers.

Large objects can be decomposed losslessly and resumed from exact child
references. Budget exhaustion creates a checkpoint, pause, or typed remainder.
The model context remains bounded per call, while the Fresta task context can
continue effectively without a fixed total window through durable memory,
retrieval, and exact resume.

## Chat, profiles, and personality

The implemented chat path is a persistent facade over existing retrieval,
attention, sheet, firewall, and controller mechanisms:

```text
chat start -> objective-relative retrieval -> attention + transcript sheet
chat say   -> persist user message -> bounded attention turn -> persist response
```

Chat history is hash-chained in its own store. The transcript sheet is a working
projection. Learning memory, user profile, and assistant personality remain
separate authorities; conversation text is never promoted merely because it was
said.

User-profile claims and assistant-personality traits already have distinct
contracts. A document using first-person language cannot create user identity.
Persistent stores, Gatekeepers, inspection, retention, and conditional
post-turn reflection are still WIP.

## Module autonomy and effects

When a capability is missing, the runtime should first try exact reuse. A model
may then propose a typed module design through `module.suggest`. It cannot
create files, install code, activate a module, or grant itself authority.

Persistent or external effects are mediated by `EffectBroker`. A plan must
declare its effects and receive a narrow grant before execution. This is not yet
strong sandboxing: community modules remain blocked until signatures,
subprocess/RPC isolation, revocation, and auditing are implemented.

## Planned interfaces

The REPL and future Web must call the same `DiamondCommandService` and public
application methods. The Web has two planned modes:

1. **Chat** — persistent conversation and controlled memory work.
2. **Workspace Agent** — project-scoped plans, file reads, patches, tests,
   diffs, approvals, checkpoints, sleep, and resume.

The Workspace Agent will never be a second uncontrolled runtime. Its flow is:

```text
LLM proposal -> controller plan -> firewall/permissions -> EffectBroker
  -> limited execution -> result/diff -> journal + checkpoint
```

Planned authority levels are `READ_ONLY`, `PATCH`, `TEST`, and `AGENT`.
Network, email, publication, installation, and credentials always require
independent grants.

# Fresta Diamond documentation

This directory contains the **English canonical documentation** for the public
Diamond WIP repository.

## Start here

1. [Project README](../README.md) — scope, status, setup, and repository map.
2. [Architecture](ARCHITECTURE.md) — executable contracts, authority boundaries,
   and dependency planning.
3. [System design](DESIGN.md) — memory, concepts, attention, chat, learning,
   module autonomy, and the planned interfaces.
4. [Operations](OPERATIONS.md) — install, tests, REPL, command runner, local
   model configuration, and benchmark lab.
5. [Benchmark protocol](BENCHMARK-PROTOCOL.md) — question-only comparison,
   Web access, bounded continuation, and current implementation boundary.
6. [Status](STATUS.md) — implemented scope, deliberate limitations, and the
   next safe milestones.
7. [Connection map](CONNECTION-MAP.md) — command, application, controller,
   effect, store, and authority boundaries.
8. [Security](SECURITY.md) — current boundary claims and what remains WIP.
9. [Ontology guide](ONTOLOGY-GUIDE.md) — user-facing explanation of Phi, F,
   the Three Orders, the Lens, and structural saturation.

## Documentary authority

- `ARCHITECTURE.md` defines the runtime contract.
- Code and tests define the behavior currently demonstrated by the contract.
- `STATUS.md` records what may honestly be claimed at this checkpoint.
- Any unimplemented design is explicitly marked **WIP**.
- Portuguese notes under [`legacy/pt`](legacy/pt/README.md) are preserved source
  material and historical context. They are not canonical release documents.

The general ontological source draft remains outside this standalone Diamond
directory. Diamond must be understandable and operable without requiring that
source corpus at runtime.

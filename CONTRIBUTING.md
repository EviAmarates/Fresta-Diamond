# Contributing to Fresta Diamond

Diamond is an early research runtime. Contributions should make the runtime
more explicit, testable, and independently operable — not merely add code.

## Before changing behavior

1. Read the project [README](README.md), [architecture](docs/ARCHITECTURE.md),
   and [current status](docs/STATUS.md).
2. State the bounded objective, affected authority boundary, expected artifacts,
   possible remainders, and external effects.
3. Prefer an existing module or public application method over a parallel path.
4. Keep the Diamond independent from imports, paths, data roots, processes, and
   configuration belonging to the original Fresta prototype.

## Change rules

- Keep model output as proposal data until existing validators/Gatekeepers have
  accepted it.
- Do not promote retrieval, chat history, documents, or similarity matches into
  confirmed memory by convenience.
- Do not treat finite missing information as `PHI`.
- Do not add unmediated filesystem, network, shell, credential, or install
  effects. Route effects through declared, reviewable boundaries.
- Preserve append-only provenance. Corrections create versions or transitions.
- Keep public operational documentation in English. Portuguese source material
  belongs under `docs/legacy/pt/`.

## Verification

Run the relevant focused tests and then the Diamond suite:

```powershell
python -m pytest -q
python scripts/run_benchmark.py --all
```

Add deterministic tests for the new behavior, including adversarial/rejection
coverage where a boundary or authority changes. Do not update a baseline simply
to hide a regression.

## Scope of this repository

This repository is being prepared as a standalone WIP. Do not commit local
runtime data, credentials, user data, cached model artifacts, or copied
Frankenstein runtime state.

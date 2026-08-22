# Diamond test data

This directory is the isolated regression laboratory for Fresta Diamond. It
does not read from or write to the original Fresta prototype's data directories.

```text
testdata/
├── manifest.json         active cases and fixture hashes
├── fixtures/             immutable inputs and recorded response bundles
├── baselines/            approved invariant projections
├── runs/                 archived new runs for comparison
├── cross/                isolated Diamond ↔ Frankenstein comparisons
├── concept-catalog/      imported heuristics and their provenance
├── adversarial-learning/ synthetic contaminated document and expectations
└── local-runtime/        ignored state from manual smoke sessions
```

`fixtures/`, `baselines/`, `cross/`, `concept-catalog/`,
`adversarial-learning/`, and archived runs are reproducible laboratory material.
`local-runtime/` is different: it contains disposable or inspectable operator
state and must never become a fixture, baseline, or production memory store.

A fixture contains a bounded object, its provenance, and a recorded response
bundle. `REPLAY` runs the real Diamond pipeline against that bundle without an
LLM, which makes contracts, validators, and Gatekeeper behavior deterministic.

`LIVE` runs use the same input but call a local LLM. Text can vary, so the
comparison focuses on stable invariants:

- technical completion and structural/epistemic closure;
- remainder types;
- crystal state and epistemic mode;
- provenance actors and locators;
- preservation of the document/user-identity boundary;
- negative-boundary observations, including `INDETERMINATE` versus
  Phi-minus `EXCLUDED`;
- candidate-concept projection without automatic promotion or intrinsic order;
- model call count.

Run from `diamond/`:

```powershell
python scripts/run_benchmark.py --list
python scripts/run_benchmark.py --all
python scripts/run_benchmark.py --case automobile-attestation
python scripts/run_benchmark.py --case automobile-attestation --live
```

Each run is archived in `runs/` unless `--no-archive` is supplied. A difference
from the baseline exits with code `2` and reports the changed fields.

## Baseline rule

A baseline is never updated automatically. Inspect a difference first; only a
deliberate review may create a new baseline and update `manifest.json`. This
prevents a new bug from becoming the expected behavior.

Fixtures may contain non-English text intentionally, because language-boundary
and prompt-boundary behavior are part of the regression corpus.

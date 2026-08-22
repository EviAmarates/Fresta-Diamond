# Baselines

A baseline is a snapshot of observable invariants, not LLM prose.

- It has an explicit version identifier.
- It excludes UUIDs, timestamps, and free-form model text.
- `scripts/run_benchmark.py` never promotes it automatically.
- A difference may be a regression, improvement, or intended behavior change;
  it requires review before the baseline changes.

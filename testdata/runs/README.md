# Archived runs

The benchmark runner writes one JSON record per run. Records preserve:

- fixture and fixture hash;
- selected baseline;
- `REPLAY` or `LIVE` mode;
- model identifier;
- invariant projection;
- observed differences.

These records are testing evidence and decision history. They may be archived
outside the repository when they grow, but they must not be rewritten.

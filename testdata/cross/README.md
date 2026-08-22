# Diamond ↔ Frankenstein comparison

This directory compares two isolated executions over the same source material.

- Diamond uses its own fixture and replay bundle.
- Frankenstein executes its centralized `/learn` path with its active blueprint.
- Every Frankenstein run uses a fresh temporary directory.
- Extraction is deterministic replay and does not call the network.
- Neither system reads or writes the other system's mutable state.

The source text is identical, but the internal contracts are not yet symmetric.
The Diamond fixture includes the structural graph proposed by its LLM operation;
Frankenstein receives only the candidate produced by its extractor. This suite
therefore compares what each pipeline does with its native representation. It
is not prompt or model parity evidence yet.

The runner normalizes only comparable properties:

- technical completion;
- candidate disposition;
- document/user boundary;
- epistemic state;
- produced persistence;
- available Phi/Phi-minus reasons and observations.

Run from `diamond/`:

```powershell
python scripts/run_cross_benchmark.py --list
python scripts/run_cross_benchmark.py --all
python scripts/run_cross_benchmark.py --case fictional-character-boundary
```

Results are compared with `cross-replay-v2`. New runs are archived in
`cross/runs/`; the baseline is never updated automatically.

# Diamond laboratory scripts

This directory contains specialized benchmarks and local-model smoke runners.
It does not define public interfaces or an alternative cognitive pipeline to the
`fresta_diamond` package.

- `run_benchmark.py` — Diamond replay/live benchmark runner.
- `run_cross_benchmark.py` — isolated Diamond ↔ Frankenstein comparison.
- `run_qwen.py` — manual controller-level ontological analysis.
- `run_learn_qwen.py` — manual learning-path smoke.
- `run_attention_qwen.py` — attention-path smoke.
- `run_objective_retrieval_qwen.py` — objective-relative retrieval smoke.
- `run_question_only_benchmark.py` — one-case question-only benchmark runner
  with explicit local model, academic search, and benchmark data-root config.
- `run_application_smoke_qwen.py` — composed learning/concept/evidence smoke.
- `run_concept_evidence_qwen.py` — concept-evidence smoke; `--resolve-gaps`
  performs the bounded research → `/learn` → revision → re-evaluation handoff
  only for validated, researchable gaps.
- `run_contaminated_learn_qwen.py` — sequential adversarial `/learn` test over
  a synthetic mixed document.
- `run_repair_qwen.py` — bounded repair over recorded rejected bundles without
  touching persistent learning memory.

Public entrypoints are intentionally kept at the repository root:
`run_commands.py` and `run_repl.py`.

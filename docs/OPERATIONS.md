# Fresta Diamond operations

## Install

Diamond is an independent Python package. From this directory:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

Requirements:

- Python 3.10 or newer;
- `pytest` for the test suite;
- an OpenAI-compatible local model endpoint only for live runs.

No API key or model endpoint is required for deterministic replay tests.

## Dedicated data roots

Every executable command requires a deliberate `--data-root`. Use a temporary
local folder for experiments:

```powershell
python run_commands.py --data-root .\local-command-data --command "/help"
python run_repl.py --data-root .\local-repl-data
```

Do not point Diamond at production memory, secrets, or the original Fresta
prototype's `data/` directory. Local runtime folders are ignored by Git.

## Shared command service

`run_commands.py` calls one slash command and emits the common JSON result:

```powershell
python run_commands.py --data-root .\local-command-data --command "/help"
python run_commands.py --data-root .\local-command-data `
  --command "/learn A car converts energy into controlled motion."
```

`run_repl.py` holds one application and one command service in memory, so that
attention foreground state, sheets, checkpoints, and commits persist between
commands:

```powershell
python run_repl.py --data-root .\local-repl-data `
  --model qwen/qwen3-14b --base-url http://127.0.0.1:1234 `
  --timeout 600 --max-tokens 4000 --attention-tokens 7000 `
  --response-tokens 2500
```

`/help` lists the current commands. `/exit` and `/quit` end the REPL only.

Current central command families:

| Family | Purpose |
|---|---|
| `/learn` | bounded text learning and controlled commit |
| `/attention` | create, turn, resume, inspect, retrieve |
| `/workspace` | create, inspect, and append cognitive sheets |
| `/chat` | start, speak, inspect, and list persistent chats |
| `/concept` | list, inspect, nominate, evaluate, resolve |
| `/module` | bounded capability design proposals and inspection |

An `INCOMPLETE` command result exits with code `3`; parsing/configuration/runtime
errors exit with `2`. Neither runner converts an incomplete model response into
success.

## Test laboratory

The test laboratory uses fixtures, baselines, and archived runs under
`testdata/`. Run deterministic replay checks with:

```powershell
python scripts/run_benchmark.py --list
python scripts/run_benchmark.py --all
python scripts/run_benchmark.py --case automobile-attestation
python scripts/run_cross_benchmark.py --all
```

Live mode calls the configured local model and should only be used with a
dedicated data root and deliberate review:

```powershell
python scripts/run_benchmark.py --case automobile-attestation --live
```

Baseline updates are never automatic. Inspect a difference first; only then
make a deliberate fixture/baseline change.

## Local-model smoke scripts

`scripts/` contains non-public experimental runners for local-model work:

- `run_qwen.py` — controller-level ontological analysis;
- `run_learn_qwen.py` — learning path;
- `run_attention_qwen.py` — attention path;
- `run_objective_retrieval_qwen.py` — objective-relative retrieval;
- `run_application_smoke_qwen.py` — composed learning/concept/evidence path;
- `run_concept_evidence_qwen.py` — concept evidence and bounded gap resolution;
- `run_contaminated_learn_qwen.py` — adversarial mixed-document learning;
- `run_repair_qwen.py` — bounded repair against recorded rejected bundles.

These scripts are useful for research and regression investigation. They are
not a stable public API and must not be treated as a replacement for the shared
command service.

## Reproducibility rules

1. Keep tests deterministic unless a test explicitly exercises a live provider.
2. Keep model, endpoint, token budget, and data root explicit in a live run.
3. Do not add personal data, secrets, or local model output to a fixture without
   a deliberate review.
4. Do not overwrite a baseline to make a failing run pass.
5. Record meaningful behavior/contract changes in `docs/STATUS.md`.

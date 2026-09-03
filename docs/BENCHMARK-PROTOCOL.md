# Historical benchmark protocol

Status: executable WIP

## Objective

Measure whether Fresta improves sustained historical analysis when the model
receives only the task question and every model call has the same bounded
context window.

The initial task is:

> Analyse the fall of the Western Roman Empire.

No causal introduction, source list, or curated answer is supplied in this
protocol. The curated Roman fixture remains a separate deterministic regression
for `/learn`.

## Comparison arms

### Closed-book

Both systems receive only the question and may not use external search. This
measures parametric model knowledge and bounded answer construction.

### Web-enabled

Both systems may research independently under the same network, query, result,
time, and token budgets.

The baseline may use the Web and its own current-call results, but receives no
Fresta memory, retrieval, sheets, journals, checkpoints, hidden summaries, or
continuation state.

Fresta may use the Web through an authorised EffectBroker path and may use its
normal controller-mediated capabilities: sheets, `/learn`, crystallization,
Φ−, journals, objective-relative retrieval, checkpoints, and resume.

This is the benchmark's practical infinite-context condition: no single model
call exceeds the bounded window, but Fresta can preserve and recover an
arbitrarily long task history through its durable stores and continuation
frontier. The baseline does not receive that cross-call context.

## Fairness rules

- The model, prompt, temperature, per-call context limit, and output budget are
  matched.
- The baseline stops when its single bounded execution is exhausted.
- Fresta may continue in additional bounded calls; this is the primary
  architectural outcome. It is effectively unbounded task context across
  calls, not infinite simultaneous model context.
- Calls, tokens, time, query counts, selected sources, source families,
  conflicts, remainders, checkpoints, and continuation are reported as costs
  and observables.
- Structural and epistemic verdicts come from the runtime contracts, not from
  an LLM judge.
- Φ remains open; Φ− records excluded alternatives and costs without granting
  authority or closing Φ.
- Network responses must be archived or content-hashed with URLs and retrieval
  times so later runs can identify Web drift.

## Current implementation boundary

The Diamond application already composes the controller, Firewall, EffectBroker,
learning memory, Φ−, sheets, retrieval, checkpoints, and persistent journals.
A deterministic question-only benchmark contract now exists: it compares a
persistent Fresta path with an isolated baseline using injectable query/search
adapters, bounded episodes, unvalidated provenance-preserving evidence, and
checkpointed continuation. The current local chat adapter still does not expose
generic model tool-calling, so a live Web-enabled run remains WIP until that
adapter path is wired and verified. A reproducible local CLI runner now exists
for one question-only case with explicit endpoint, model, search, and data-root
configuration.

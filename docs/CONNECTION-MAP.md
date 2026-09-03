# Runtime connection map

This map records the current path from a user-visible command to an
auditable, bounded result. It is descriptive, not an additional authority
layer: `ARCHITECTURE.md`, the code, and the tests remain authoritative.

```text
command service
  -> DiamondApplication facade
  -> typed request / bounded objective
  -> blueprint + module registry
  -> controller plan resolution and validation
  -> constitutional firewall attestation
  -> EffectBroker grant (only when an effect is needed)
  -> operation/provider execution
  -> validator and Gatekeeper
  -> append-only journal/store or typed remainder
  -> command result / checkpoint
```

## Boundary ownership

| Surface | Owns | Does not own |
|---|---|---|
| Command service | Parsing, dispatch, read-only presentation | Ontological validation, direct effects |
| `DiamondApplication` | Composition of stores, controllers, and domain flows | Model authority or hidden persistence |
| Blueprint | Required inputs, outputs, effects, and closure obligations | Provider choice or truth |
| Module registry | Admission and capability/schema discovery | Invocation, O1/O2/O3 assignment |
| Controller | Plan resolution, validation, scheduling, and state transitions | Unbounded work or implicit grants |
| Constitutional firewall | Objective admissibility and constitutional depth | Semantic truth or provider output |
| `EffectBroker` | Short-lived, scoped authorization and effect audit | Expanding permissions |
| Domain Gatekeeper | Profile adoption and other promotion decisions | Automatic promotion by confidence |
| Stores and journals | Versioned, hash-checked append-only state | Rewriting history |

## Main command paths

| Command family | Application path | Durable result |
|---|---|---|
| `/learn` | bounded proposal -> learning validator | learning-memory commit or remainder |
| `/chat` | chat lifecycle -> optional reflection proposal | sealed transcript and lifecycle history |
| `/profile` and `/personality` | proposal -> inspection or explicit adoption | `PROPOSED` or new `ACTIVE` lineage |
| `/brain analyze` | deterministic inventory and ontology diagnosis | immutable report with `phi_open` |
| `/document` | UTF-8 intake -> lossless sheets -> bounded `/learn` leaves | checkpoint, commits, or pending refs |

## Authority and closure

Retrieval nominates candidates; it does not provide constitutive O2 evidence.
O1, O2, O3, and FILTER are contextual to the bounded object and objective.
Operational completion means that the declared finite work has been processed or
left as an explicit typed remainder. It is not epistemic closure and never
closes constitutional PHI.

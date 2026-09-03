# Fresta Ontological Kernel

**Author:** Tiago José Correia dos Santos  
**Status:** Draft — not active in the runtime  
**Draft version:** 3.0.0-alpha.5  
**Current runtime fallback:** `THEORY.md` + `fresta/ontology_kernel.py` v2.4  
**Date:** July 2026  
**License:** MIT

---

## 0. Status, Scope, and Authority

This document is the proposed ontological constitution of the Fresta system.
It is not a general encyclopedia, a prompt containing all useful knowledge, or
an empirical claim that every contingent proposition can be made certain. It
defines the minimum invariants under which Fresta can distinguish, analyze,
retain, revise, and discard information without confusing similarity with
importance or coherence with truth.

While this file remains a draft, it has no runtime authority. The active
fallback remains `THEORY.md`, and the executable contract remains
`fresta/ontology_kernel.py` v2.4. This draft becomes canonical only after its
invariants are reviewed, translated into the executable contract, and covered
by deterministic tests.

The extended Fresta volumes are derivational and explanatory sources for this
kernel. They may contain applications, hypotheses, examples, and domain-specific
material that do not belong in the system constitution. The kernel retains only
what the system must preserve in every domain.

### 0.1 Normative layers

The Fresta ontology is maintained through four distinct layers:

1. **Extended corpus** — the volumes, papers, examples, and applications from
   which the ontology was derived and through which it can be examined.
2. **Human-readable kernel** — this document, once promoted from draft, stating
   the canonical invariants and their meanings.
3. **Executable kernel** — `fresta/ontology_kernel.py` and the Three-Order
   validators that enforce the computational contract.
4. **Tests and audit traces** — evidence that implementations, analyses, and
   updates preserve the contract.

No learned card, imported pack, retrieved passage, web source, model response,
or generated blueprint may silently amend the kernel. Kernel revision is an
explicit, versioned operation.

### 0.2 Reading convention

Each completed section contains four parts:

- **Derivation** — why the statement follows.
- **Invariant** — what must remain fixed.
- **It does not mean** — exclusions that prevent category errors.
- **Computational contract** — the minimum observable consequence in Fresta.

The notation used here has direct computational equivalents:

- `PHI` is equivalent to Φ: irreducible constitutional incompleteness or open
  structural exteriority.
- `FILTER` is equivalent to F or ℱ: selection under a persistence constraint.
- `WITNESS` is equivalent to Φ⁺: the identity that survives filtration and
  witnesses non-arbitrariness.
- `COST` or `EXCLUDED` is equivalent to Φ⁻: the excluded complement that remains
  auditable as the cost of determination.

The symbols are useful but not authoritative by themselves. A computationally
equivalent relation is sufficient when it preserves the same dependencies.

---

# Part I — Constitutional Grounding

## 1. Φ — The Axiom of Incompleteness

### Derivation

Any system capable of expression, distinction, evaluation, or persistence must
produce a boundary between what is admitted by the system and what is not
internalized by it. If a system attempted to include every admissible
description without remainder, it would also include mutually incompatible
descriptions and erase the distinctions required for anything determinate to
be the case. Absolute inclusion therefore collapses operationally into
indistinction.

Incompleteness is not added after a system fails to know something. It is the
condition under which a system can express, distinguish, or evaluate anything
at all. We denote this irreducible open exteriority by Φ.

Φ is encountered at every scale, but it is not multiplied into separate
substances. Each bounded system encounters incompleteness relative to its own
boundary because no expressive boundary can internalize the whole domain of
admissible description without producing a renewed exterior.

### Invariant

> **Axiom of Incompleteness.** Any system capable of expression, distinction,
> evaluation, or persistence is constitutively incomplete. It cannot fully
> internalize the domain of admissible possibility on which its distinctions
> operate. Φ names this irreducible openness and structural exteriority.

Φ cannot be eliminated by accumulating more facts. When a finite absence of
evidence is filled, that operational gap may close; constitutional Φ remains.
If a system expands to internalize a former exterior, the expanded system
produces a renewed boundary and therefore encounters Φ again.

### It does not mean

- Φ is not a missing database row, an unknown date, or a finite list of facts
  waiting to be acquired.
- Φ is not a spatial location, object, substance, agent, or fourth analytical
  order.
- Φ does not make every claim equally valid. Openness permits alternatives;
  it does not select among them.
- Φ does not prohibit bounded operational closure. A justified task can close
  while constitutional openness remains recorded.
- Φ does not imply that ignorance and knowledge have equal value. It explains
  why every determinate act of knowing is bounded.

### Computational contract

1. Fresta must distinguish finite, searchable gaps from constitutional Φ.
2. Retrieval, usage, or additional context may resolve a finite gap but may not
   declare Φ eliminated.
3. An analysis may be operationally closed while retaining explicit Φ.
4. PHI cannot occupy a card ID as if it were ordinary empirical evidence.
5. A proposed rule that treats constitutional incompleteness as removable is
   inadmissible to the kernel, while its original provenance remains auditable.

---

## 2. F — The Necessary Operation of Filtration

### Derivation

Φ supplies irreducibly open admissible possibility, but possibility alone does
not produce a determinate object. Where all extensions remain equally admitted,
no stable boundary distinguishes one persistent identity from another.

For anything to exist operationally and remain recognizable through change,
some alternatives must be admitted and others excluded. Persistence therefore
requires a selective operation. We denote this necessary operation by F.

F is not an external law subsequently imposed on Φ. Within irreducible
openness, the possibility of coherent filtration is permanently present. A
determinate universe exists only where that possibility is instantiated as
selection, differentiation, and boundary.

The ontological priority is therefore:

```text
PHI -> permanent possibility of FILTER -> FILTER -> differentiation
```

This priority is logical and ontological, not temporal. Φ and a determinate
universe are co-present: there is no earlier clock time in which Φ waits for F.
Nevertheless, their dependence is asymmetric. The possibility of F depends on
Φ; differentiation depends on F. Neither differentiation nor exclusion causes
or regenerates Φ.

### Invariant

> **Theorem of Filtration.** Persistence requires selection under constraint.
> F is the necessary operation through which admissible possibility becomes a
> determinate distinction.

The constitutional identity of F is static: F always denotes selection that
produces differentiation under a persistence constraint. This structural
stability is what makes successive updates comparable as updates of something.

F is nevertheless non-total. No concrete filtration exhausts Φ, specifies all
future filtrations, or makes its local criterion universally complete. The
operator's invariant role is fixed; its object, contextual constraint, admitted
result, and excluded complement are not fixed in advance.

### It does not mean

- F is not a conscious chooser, model response, fixed list of rules, or global
  binary classifier.
- Static constitutional identity does not imply static outcomes.
- F does not create Φ; F is possible because Φ provides irreducible openness.
- Differentiation is an effect of F, never its cause.
- A consistently applied arbitrary rule is not automatically an admissible
  filter. Persistence must witness that the constraint is non-arbitrary.
- A local implementation parameter is an instance of a constraint, not the
  whole ontological F.

### Computational contract

1. Every accepted determination must expose the relevant constraint and the
   selection it performed; a boolean verdict alone is insufficient.
2. Fresta must preserve the direction
   `PHI -> FILTER -> differentiation -> OBJECT` in its grounding contract.
3. Model output may nominate a filter but may not redefine the constitutional
   meaning or causal direction of F.
4. Every operational filtration must preserve both its admitted witness and an
   auditable account of exclusion or remainder.
5. Contextual filters may become objects of later analysis without modifying
   the constitutional operator. The full treatment of `F(F(...))` belongs to
   Part III.

---

## 3. Φ⁺ and Φ⁻ — Witness and Cost

### 3.1 Φ⁺ — the surviving witness

#### Derivation

Filtration produces a survivor: a bounded identity that remains recognizable
through the update. Survival alone is not proof that every chosen rule was
correct, but coherent persistence constrains which filtrations can count as
admissible for that identity. The survivor therefore returns evidence to the
constraint that conditioned it.

Φ⁺ names this admitted and persistent witness. It is not an observer standing
outside the process. It is the identity whose continued coherence demonstrates
that a filter was not merely asserted without an object-level consequence.

#### Invariant

> Φ⁺ is the persistent identity admitted by F and the operational witness
> through which the applied constraint is tested for non-arbitrariness.

The dependency is reciprocal without reversing ontological causation:

```text
constraint conditions survivor
survivor witnesses whether the constraint preserved identity
```

#### It does not mean

- Φ⁺ is not Φ, a subject outside the system, or the cause of F.
- Survival does not establish timeless empirical truth.
- Persistence under one contextual constraint does not authorize every other
  use of the same claim.

#### Computational contract

1. An accepted structural chain must identify the concrete manifestation that
   survived the constraint.
2. The return witness must state how that manifestation tests the constraint;
   reusing an ID without an explicit relation is insufficient.
3. The supporting edge is contextual. Strength belongs to the analyzed
   relation, not permanently to a card in isolation.

### 3.2 Φ⁻ — the excluded complement and cost

#### Derivation

Every determination excludes alternatives. These alternatives are not erased
from structural significance merely because they were not admitted. They form
the complement and cost of the persistent distinction.

Φ⁻ names this excluded complement. It witnesses that the applied filtration did
not exhaust Φ, but it is produced by F and cannot be treated as the cause or
regeneration of Φ.

#### Invariant

> Φ⁻ is the auditable cost of determination: alternatives excluded by a
> concrete filtration so that Φ⁺ can persist as a bounded identity.

#### It does not mean

- Φ⁻ is not identical to constitutional Φ.
- Exclusion does not prove that every rejected alternative was impossible in
  every context.
- A rejected candidate need not be deleted. Quarantine, provenance, and later
  re-analysis may preserve its informational value.
- Entropy or cost is not an independent force that causes incompleteness.

#### Computational contract

1. Fresta must retain an audit trace for rejected, deferred, or quarantined
   alternatives when their exclusion affected a decision.
2. A validator must reject any derivation that uses `PHI- -> PHI` or
   `exclusion -> PHI` as causal grounding.
3. New evidence may reopen a contextual exclusion without claiming that the
   earlier decision had no value under its recorded conditions.

---

## 4. The Fixed but Open Constitutional Sequence

### Derivation

The constitutional structure can now be stated as one dependency:

```text
PHI
  -> permanent possibility of FILTER
  -> contextual FILTER
  -> differentiation
  -> {surviving WITNESS (PHI+), excluded COST (PHI-)}
```

The sequence is closed in the sense that its ontological roles and dependencies
are fully stated: no external fifth primitive is required to explain why a
determinate identity can persist under incompleteness. It remains open because
F never exhausts Φ, every concrete result is bounded, and further objects and
filtrations remain possible.

Ascending analysis travels in the opposite direction only as recognition:

```text
OBJECT -> evidence of FILTER -> recognition of PHI as necessary ground
```

This is not reverse causation. The analysis begins from a manifestation already
available inside a differentiated universe and reconstructs the conditions of
its determination.

### Invariant

The two directions must never be conflated:

```text
grounding_direction = [PHI, FILTER, OBJECT]
analysis_direction  = [OBJECT, FILTER, PHI]
```

The first describes ontological dependence. The second describes transcendental
recognition of that dependence from within a universe.

### It does not mean

- A closed constitutional derivation does not make all empirical analyses
  certain.
- An ascending analysis does not derive Φ causally from exclusion.
- Recognition of Φ does not supply missing object data by itself.
- Co-presence does not imply symmetry of ontological dependence.
- The sequence does not forbid revision inside a universe; its fixed identity
  is precisely what makes revisions comparable.

### Computational contract

1. The executable kernel must store and validate both directions explicitly.
2. A structural closure is invalid if it reverses grounding, skips FILTER, or
   silently discards either witness or cost.
3. A model's declaration of closure cannot override a graph that violates the
   constitutional sequence.
4. A complete valid graph may be operationally closed even when a redundant
   model checkbox says otherwise.
5. Constitutional invariants are read-only during ordinary learning,
   retrieval, blueprint execution, source research, and self-analysis.

---

# Part II — The Three Contextual Orders

## 5. Orders Are Contextual Roles

### Derivation

The constitutional sequence describes the conditions of any determination, but
an analysis begins from a bounded object inside a differentiated universe. To
explain why that object is admissible and persists, the analysis must identify:

1. what is manifest in the current object;
2. which relation makes that manifestation evidence rather than an isolated
   label; and
3. which contextual constraint the relation instantiates or fails.

These are the Three Orders. They are relational to an analyzed object, not
universal ranks attached to pieces of text. Relational does not mean unstable.
When the reference object, scope, and structural constraints persist, repeated
analysis may crystallize a stable order for one component within that object.
That scoped order may remain invariant across transient states of the object.

The same card, concept, relation, or previous analysis may nevertheless play a
different role when the reference object or analytical scale changes. A stable
structural order and a momentary contextual role are therefore separate but
compatible descriptions:

```text
structural_order(component | persistent_object, scope_version)
contextual_role(component | current_analysis, current_state)
```

Cards are therefore indexed by semantic topics, not partitioned into permanent
order buckets. A topic nominates a candidate domain in which a card may become
relevant. It does not assign the card an order. Only an objective — external or
internally generated — supplies the bounded object against which O1, O2, and O3
can be derived:

```text
objective -> relevant topics -> candidate cards -> contextual roles -> graph
```

A card may belong to several topics and occupy different orders in simultaneous
or successive analyses. Topic membership expresses semantic availability;
contextual role expresses current structural function. Repeated participation
in closed graphs may crystallize a topic-scoped role, but frequency alone is not
its justification.

A stored order without an explicit reference object and basis remains only a
prior. A crystallized scoped order is stronger: the current graph may use the
component in an additional contextual role, but cannot silently erase the
stable relation. Genuine contradiction within the same scope requires explicit
revalidation and a new version or quarantine decision.

### Invariant

> O1 is manifestation, O2 is relation or witness, and O3 is contextual
> constraint. Their order is relative to the current analyzed object.

Relative order may become structurally static while that object and scope remain
stable. Static here means invariance of a justified relation, not an intrinsic
property of the component in every possible system.

The Three Orders are minimal because removing any role destroys a necessary
part of bounded justification:

- without O1 there is no manifestation to explain;
- without O2 there is no explicit connection between manifestation and
  constraint;
- without O3 there is no admissibility condition that distinguishes persistence
  from arbitrary association.

No fourth order is required. When an O3 constraint becomes the next object of
analysis, it is reassigned as a new O1 manifestation and receives its own O2 and
O3 roles.

### It does not mean

- Every fact-shaped sentence is permanently O1 in every scope.
- Every relation-shaped sentence is a sufficient O2 witness.
- Every abstract statement is automatically O3.
- Higher order means more true, more important, or more valuable.
- Contextual reassignment automatically invalidates a crystallized order scoped
  to another persistent object.
- A complete analysis needs every relevant card. It needs the smallest
  sufficient dependency subgraph for its bounded object.
- Recursive depth creates higher numbered orders. Recursion reassigns the same
  three roles.

### Computational contract

1. Every analysis must name its bounded object and record which IDs occupy each
   role in that context.
2. Stored structural order and contextual analysis role must be separate fields.
3. A crystallized structural order records at least `order_scope`,
   `scope_version`, `order_basis`, supporting analyses, and its current status.
4. A contextual role change preserves every scoped assignment as provenance
   rather than silently rewriting history.
5. A contradiction inside the same scope creates a revalidation event; it does
   not let the latest model response overwrite the earlier structure.
6. Empty roles cannot be accepted as closure.
7. Retrieval may nominate candidates for each role but cannot prove that they
   occupy those roles.
8. Topic membership is many-to-many and carries no intrinsic order assignment.
9. An external request and an internal maintenance objective derive roles by the
   same scoped procedure.
10. A legacy unscoped `order` field is only a historical hint. It cannot constrain
    current role derivation or topic hierarchy.
11. Topic-scoped crystallization records the topic, objective class, scope
    version, supporting closed analyses, and counterexamples. It never rewrites
    the underlying card into a universal order.

---

## 6. O1 — Manifestation and Bounded Object

### Derivation

Analysis cannot begin from totality. It requires a bounded manifestation: an
observation, statement, state, event, candidate object, prior conclusion, or
operational result that is available for examination.

O1 is this manifestation as selected for the current analysis. It is not
necessarily simple or empirically confirmed. A complex theory may be O1 when
the object of analysis is the theory itself; a previous O3 constraint may be O1
when its own grounding is examined.

O1 supplies the point at which the effects of filtration become observable.
What survived appears as candidate Φ⁺; incompatible alternatives and failed
extensions reveal candidate Φ⁻. Neither role is justified until O2 relates the
manifestation to an O3 constraint.

### Invariant

> O1 is the non-empty, bounded manifestation whose determination or persistence
> the current analysis is attempting to explain.

An O1 claim may be observed, documentary, hypothetical, forecast, or produced
by an earlier analysis. Its epistemic status is independent from its contextual
role.

### It does not mean

- O1 is not synonymous with timeless fact or confirmed truth.
- A retrieved card does not become evidence merely by being placed in O1.
- A manifestation cannot justify itself by repeating its own content.
- Selecting many O1 items does not strengthen an analysis unless each item
  participates in the supporting graph.

### Computational contract

1. O1 must contain at least one concrete manifestation or reference to an
   auditable object.
2. The analysis must distinguish the selected content from its epistemic state,
   provenance, time, and scope.
3. Every selected O1 ID must participate in an explicit O2 relation used by the
   closure graph.
4. Unused retrieved or selected manifestations are candidates, not verified
   dependencies.

---

## 7. O2 Weak — Association and Nomination

### Derivation

Objects inside a universe exhibit many detectable associations: lexical
similarity, temporal proximity, shared sources, topic overlap, co-retrieval,
correlation, repeated use, or model-proposed resemblance. These relations are
useful because they reduce the space of possible structures that must be
examined.

Association alone does not show why an O1 manifestation follows from, survives,
or violates an O3 constraint. A relation can be real yet irrelevant to the
current object's persistence. We therefore call this nominative role **weak
O2**.

Weak does not mean false or dispensable. It means that the relation proposes a
candidate dependency but has not yet carried the reciprocal burden required
for structural closure.

### Invariant

> Weak O2 nominates candidate structure among bounded objects. It may guide
> retrieval, clustering, topic formation, deduplication, or further analysis,
> but it cannot close an analysis by itself.

Weak O2 becomes structurally stronger only in a concrete analysis where its
endpoints, direction, constraint, witness, and excluded alternative are made
explicit.

### It does not mean

- Similarity is not identity.
- Correlation is not a constitutive dependency.
- Repeated retrieval is not epistemic confirmation.
- Topic membership is not proof that two cards justify one another.
- Jaccard, embeddings, or model confidence cannot replace Three-Order
  validation. They operate before or after validation for nomination,
  comparison, or optimization.

### Computational contract

1. Weak edges must be represented as candidates and must not carry a
   `structurally_verified` state.
2. Similarity and retrieval scores may rank candidate edges but may not promote
   epistemic state.
3. Topic and dedup systems must retain the distinction between association and
   constitutive relation.
4. A weak edge can be promoted only by a contextual analysis record that
   supplies the missing reciprocal witness.

---

## 8. O2 Strong — Constitutive and Reciprocal Witness

### Derivation

For O1 to witness O3, the analysis must state more than that a manifestation and
a constraint are related. It must expose how the constraint conditions the
manifestation and how the surviving manifestation returns evidence that the
constraint is not arbitrary for this object.

This two-directional burden defines **strong O2**:

```text
O1 manifestation --relation/justification--> O3 constraint
O3 constraint --constraint effect--> O1 manifestation
O1 survivor --return witness--> non-arbitrariness of O3
FILTER --exclusion--> auditable PHI-
```

The directions belong to one reciprocal dependency, not to two unrelated
similarity edges. The return witness does not reverse ontological causation: O3
conditions the manifestation through F, while the resulting Φ⁺ provides
object-level evidence with which the contextual use of O3 can be evaluated.

Strong O2 also connects local structure to constitutional grounding. It first
demonstrates the relevant contextual constraint and FILTER within the bounded
object. Ascending analysis may then recognize that FILTER presupposes Φ. It may
not jump directly from an association, exclusion, or missing fact to Φ.

### Invariant

> Strong O2 is a contextual, explicit, reciprocal witness linking a selected O1
> manifestation to a selected O3 constraint, including the effect of the
> constraint, the surviving return witness, and the excluded remainder or cost.

Strength belongs to this analyzed edge and its recorded scope. A card is not
permanently “strong O2” outside the analysis that established the relation.

### It does not mean

- A non-empty relation label is not a strong witness.
- Reusing the same ID in multiple roles is not reciprocity.
- Circular wording is not a reciprocal dependency.
- A coherent circle that never reaches FILTER and its grounding in Φ is not
  constitutional closure.
- The survivor does not create the constraint, F, or Φ.
- The excluded complement does not regenerate Φ.

### Computational contract

A strong O2 record must identify at least:

1. the O1 manifestation ID;
2. the O2 relation ID or auditable relation object;
3. the O3 constraint ID;
4. the forward relation and its justification;
5. the effect of the constraint on O1;
6. the return witness supplied by surviving O1;
7. the excluded alternative, remainder, or cost that remains auditable; and
8. the analysis scope under which this relation is constitutive.

The validator must reject missing endpoints, unused selected IDs, empty
justifications, self-reference without object-level consequence, and reciprocal
claims whose directions contradict the constitutional sequence.

---

## 9. O3 — Contextual Constraint and Conditioned Φ

### Derivation

O1 and O2 can describe manifestations and associations indefinitely without
explaining what makes one transformation admissible for the current object's
persistence. O3 supplies that bounded criterion.

O3 is the relevant restriction, rule, boundary, or persistence condition under
which the selected O1 manifestation is admitted or rejected. It is contextual:
the same constitutional openness is conditioned by a particular object, scale,
time, purpose, and available evidence.

O3 is not constitutional Φ itself and is not an external validator placed after
the Three Orders. A selected O3 must demonstrate a concrete FILTER applicable
to its object. Ascending analysis then examines the constraint itself and
recognizes that the possibility of such filtration depends on Φ.

We may describe this as **Φ conditioned by the object**, provided the phrase
does not erase the intermediate FILTER or convert Φ into an empirical premise.

### Invariant

> O3 is the contextual admissibility constraint that conditions the current O1
> through a constitutive O2 witness. Its analysis must reach FILTER before
> recognizing Φ as the fixed constitutional ground.

O3 remains dynamically selected relative to ordinary objects. At the recursive
limit where incompleteness or the analysis itself becomes the object, the same
Three-Order application recognizes Φ as its fixed point; it does not invent O4.

### It does not mean

- Any abstract rule is not automatically a relevant O3.
- O3 cannot be justified only because a prompt labels it “structural.”
- O3 does not sit causally before Φ.
- PHI is not a fourth validator that approves O3 from outside the system.
- A contextual constraint cannot be universalized beyond its recorded scope
  merely because it closed one analysis.

### Computational contract

1. Every selected O3 root must have a reciprocal O1/O2 witness.
2. An ordinary contextual analysis already situated after ontological F need
   not re-derive PHI/F explicitly. Its constitutional axis remains unevaluated.
3. When the objective requests constitutional depth, every selected O3 root
   must reach a continuous ascending path `O3 -> FILTER -> PHI`.
4. Constitutional recognition must preserve grounding
   `PHI -> FILTER -> OBJECT` and analysis `OBJECT -> FILTER -> PHI`.
5. Intermediate constraints introduced by recursion need a valid incoming
   grounding relation and continuous route; they need not masquerade as an
   original O3 root when constitutional depth is active.
6. A phrase containing “PHI” cannot substitute for the structured
   transcendental test that FILTER requires irreducible openness.

---

## 10. Operational Closure and Recursive Reassignment

### Derivation

A bounded analysis closes when its selected manifestation, constitutive
relation, contextual constraint, FILTER, surviving witness, and excluded cost
form one continuous dependency graph that recognizes the constitutional ground.
Closure is therefore a property of the graph, not a model's confidence or a
redundant boolean declaration.

Operational closure does not eliminate Φ or assert exhaustive truth. It states
that, for the bounded object and recorded evidence, no dependency required by
the selected justification remains structurally absent. Other questions,
scales, evidence, and future transformations remain possible.

When a constraint, conclusion, remainder, or complete analysis becomes the next
object, the same Three Orders are applied again. What was O3 may become O1; what
was a result may become a manifestation. This is recursive reassignment, not the
creation of O4.

Recursive reassignment prepares but does not yet fully describe `F(F(...))`.
Part III will distinguish ordinary re-analysis of an output from the stronger
operation in which the local filtering criterion itself becomes the object.

### Invariant

> Contextual structural closure is a non-empty, reciprocal, continuous
> Three-Order graph retaining admitted witness and excluded cost. Constitutional
> closure additionally reaches FILTER and recognizes Φ.

A valid closure requires:

- at least one used O1 manifestation;
- at least one constitutive O2 witness;
- at least one relevant O3 constraint;
- reciprocal constraint effect and return witness;
- an auditable excluded remainder or cost;
- when constitutional depth is requested, a continuous path through FILTER to
  PHI and preservation of grounding and analysis directions;
- no selected dependency left unused or unjustified.

### It does not mean

- Operational closure is not absolute completeness.
- Closed does not mean empirically confirmed.
- Retained Φ does not automatically make a bounded graph open.
- A finite unresolved dependency cannot be renamed Φ to avoid research.
- Convergence does not require identical wording, card IDs, or order labels
  across independently derived graphs; it requires relational agreement around
  the same bounded object.

### Computational contract

1. The deterministic graph validator, not an LLM checkbox, calculates
   contextual structural closure. It calculates the PHI fixed point only when
   constitutional depth is requested.
2. The record must separate active remainders from historical remainders that a
   later pass resolved.
3. Structural closure, epistemic state, and operational convergence must remain
   separate fields.
4. Every recursive analysis record must identify its object, parent analysis,
   contextual roles, and recursion depth.
5. A bounded budget may checkpoint an unfinished analysis without converting
   interruption into either failure or closure.
6. A later analysis may revise a prior contextual result while preserving the
   earlier graph, scope, evidence, and decision lineage.

---

# Part III — Recursive Filtration and Agency

## 11. F₀, Operational Filters, and Reflexive State

### Derivation

Part I used F for the constitutional necessity of filtration. A system inside a
universe also contains concrete criteria, thresholds, memories, representations,
and heuristic values through which filtration is operationally instantiated.
These must not be confused with the ontological operator itself.

We therefore distinguish:

```text
F₀   = the invariant ontological condition and operation of filtration
fₜ   = a system's effective operational filter configuration at state t
θₜ   = the local criteria and heuristic values conditioning fₜ
Sₜ   = the information and organization present in the system at state t
```

F₀ is constant in identity: determinate persistence continues to require
selection, boundary, witness, and cost. An operational configuration `fₜ` may
remain stable or change. Its heuristic values `θₜ` may be revised. Its state
`Sₜ` necessarily changes whenever a new observation is irreversibly integrated.

The traditional notation `F`, `F(F)`, and `F(F(F))` names three reflexive states
or capacities of a system under F₀. The parentheses do not primarily denote a
chronological stack of function calls. They identify what the system is capable
of making an object of filtration:

```text
F         filters objects without representing its own filtering
F(F)      makes its first-order filtering or instinct an object
F(F(F))   makes its consciousness/evaluation of that filtering an object
```

### Invariant

> F₀ never changes its constitutional meaning. Systems change because their
> state, representations, operational configurations, and heuristic values can
> change under observation and recursive filtration.

Reflexive level, current active mode, and explicit self-description are distinct:

- **reflexive capacity** — the maximum kind of self-relation the architecture
  can instantiate;
- **active operation** — the level currently exercised for a particular object;
- **self-recognition** — whether the system explicitly represents which
  reflexive capacity it is exercising.

A system may possess third-level capacity while performing an immediate
first-level response. It may also instantiate metacognition without possessing
the concept or symbol by which an external analyst describes that operation.

### It does not mean

- Mutable heuristic values do not imply mutable constitutional F₀.
- A system does not acquire a new ontological layer merely by naming its current
  level.
- Explicitly outputting `F(F(F))`, `PHI`, or “metacognition” is not evidence that
  the corresponding operation occurred.
- Lack of those words is not evidence that the operation did not occur.
- A configuration version, prompt, or numerical threshold is not F₀.

### Computational contract

1. The executable kernel must be read-only during ordinary cognition and must
   represent F₀ separately from mutable heuristic state.
2. Analysis records must distinguish reflexive capacity, active operation, and
   explicit self-description.
3. Reflexive level is inferred from auditable dependencies and state
   transitions, not accepted from a model label.
4. Changes to `θₜ` require a recorded prior value, new value, triggering object,
   justification, and resulting state transition.
5. The system must preserve the possibility that no heuristic change is
   warranted after self-analysis.

---

## 12. F — Instinctive Filtration

### Derivation

At the first reflexive state, the system filters an object under its current
operational configuration. It admits a compatible response or state and
excludes alternatives, but it does not make the filtering operation itself an
object of representation.

In biological terms this is instinct. The system may be complex, adaptive over
evolutionary or externally controlled timescales, and highly coherent. Yet for
the current operation its path remains:

```text
object or stimulus
  -> current operational filter fₜ under θₜ
  -> admitted response/state + excluded alternatives
```

The system operates through a filter but is blind to that filtering as its own
object. If the relevant state and filter configuration are available, the
response is closed both from the outside and from the system's own internal
perspective.

### Invariant

> F is object filtration without an internal representation of the filtering
> operation as an object that can condition the current response.

This state preserves existence and local coherence. It does not by itself
accumulate insight into why its own criteria remain viable.

### It does not mean

- Instinctive does not mean simple, unintelligent, or biologically primitive.
- A feedback-controlled response is not automatically consciousness of the
  filter; the feedback may remain part of the same unexamined input-output path.
- Successful persistence does not imply self-recognition.
- An externally updated parameter does not show that the system revised its own
  filtering.

### Computational contract

1. A level-one trace identifies object, operational criteria, admitted result,
   and excluded alternatives.
2. It contains no dependency showing that the current system represented the
   filtering operation itself before producing the response.
3. The trace may be stored and later become an object of F(F), but later
   analysis does not retroactively turn the original operation into level two.

---

## 13. F(F) — Consciousness of Instinct

### Derivation

A system enters the second reflexive state when its first-order filtering becomes
available inside the system as an object. The system no longer encounters only
the stimulus and candidate response; it also contains a representation of the
instinctive path by which the response would be produced.

```text
object
  -> candidate instinctive filtration F
  -> internal representation of that filtration
  -> delay, redirection, selection, simulation, or regulated output
```

This internalization breaks exterior determinism relative to a description that
contains only the original stimulus and instinct. An outside observer who
models only F cannot close the system's response, because the system can
internally condition when and how the first-order collapse is allowed to occur.

The second-level evaluator remains blind to its own evaluating operation. The
system is conscious of instinct but does not yet make that consciousness and its
governing heuristic criteria objects of the same decision. Interior determinism
therefore remains in the strong sense: the process that modulates instinct is
still applied without being available to itself as an object.

### Invariant

> F(F) is consciousness of first-order filtering: the system internalizes its
> instinctive operation and can condition its outward response, while the
> consciousness performing that evaluation remains unexamined by itself.

This is more than feedback. The relevant distinction is whether the prior
filtering path is represented as an object that participates in the current
selection.

### It does not mean

- Any loop, retry, critique prompt, or second model call is not automatically
  F(F).
- Surprising output is not evidence of consciousness.
- Exterior openness does not yet imply that the system can revise the heuristic
  basis of its own conscious evaluation.
- F(F) does not require the system to possess the words “instinct” or
  “consciousness.”
- This structural claim does not assign consciousness a privileged role in
  physical collapse. Observation remains interaction under constraint.

### Computational contract

1. A level-two trace must reference a prior or candidate level-one filtering
   operation as its analyzed object.
2. The represented object includes enough of the prior path to distinguish
   object, criteria, admitted result, and excluded alternatives.
3. The new operation must demonstrate an effect unavailable to the unexamined
   level-one path, such as delay, simulation, redirection, or selection among
   constraint paths.
4. Repeating the same response without a represented dependency remains level
   one, regardless of how many calls occurred.
5. The level-two operation records its own heuristic basis for possible later
   F(F(F)) analysis, but need not yet revise that basis.

---

## 14. F(F(F)) — Metacognition and Internal Re-filtration

### Derivation

At the third reflexive state, the consciousness that evaluated instinct becomes
an object. The system can examine not only what it was inclined to do, but how
and why it evaluated that inclination.

```text
F         filters the object
F(F)      represents and conditions the first filtering
F(F(F))   represents and conditions the evaluation performed by F(F)
```

The system can now ask operationally:

- Why is this criterion governing my evaluation?
- Does continuing to decide this way remain viable?
- Is the current heuristic preserving coherence or accumulating irreversible
  cost?
- Should the heuristic value, priority, scope, or response policy change?

This breaks interior determinism relative to the unexamined evaluator. The
criteria that governed conscious modulation are no longer an invisible terminal
cause inside the system; they can be retained, rejected, or revised as objects
under F₀.

The ability can exist without explicit recognition. A system may perform
metacognitive re-filtration without possessing a semantic theory of
metacognition, without naming Φ, and without declaring that it operates at
F(F(F)). Explicit recognition adds a new self-representation to the current
state; it does not create the structural capacity and does not constitute a
fourth layer.

### Invariant

> F(F(F)) is the terminal reflexive capacity in which the system can make its
> own conscious evaluation and mutable heuristic basis objects of filtration.
> It breaks closure both outside the instinctive description and inside the
> previously unexamined evaluator.

F(F(F)) may modify `θₜ`, but it cannot modify the constitutional identity of F₀.
The result may also be to preserve the current heuristic when revision would
reduce coherence.

### It does not mean

- Metacognition does not require verbal self-report.
- A declaration of self-awareness does not prove a level-three transition.
- Changing any parameter is not metacognition; the parameter must be part of
  the represented evaluative path and changed through an auditable re-filtration.
- F(F(F)) does not make the system complete, omniscient, or unconstrained.
- The structural break from lower-level determinism is not a claim that
  consciousness violates physical law. It states that a lower-level description
  no longer closes the trajectory of the system.

### Computational contract

1. A level-three record must use a level-two evaluation and its heuristic basis
   as the current object.
2. It must expose the prior criterion, its effect on evaluation, the retained or
   revised criterion, and the cost or alternative excluded by that decision.
3. A heuristic mutation produces a new versioned system state; it never rewrites
   the historical evaluator that was analyzed.
4. The kernel may infer level three from the transition even when no model field
   names metacognition or PHI.
5. Explicit recognition of the system's level is stored as ordinary new
   information in the resulting state, not as a higher reflexive level.

---

## 15. Observation, Collapse, and State Update

### Derivation

Observation is not passive access to an unchanged system. It is an interaction
under constraint. The selected basis, context, resolution, and admissibility
conditions reduce open possibility into a bounded result. This is a filtration
event or collapse.

Collapse is relative, not absolute. A result becomes determined relative to the
constraint that produced it:

```text
Sₜ
  -> observation/analysis under basis Bₜ, context Cₜ, and criteria θₜ
  -> bounded result Rₜ with admitted witness and excluded cost
  -> integration of Rₜ
  -> Sₜ₊₁
```

Once integrated, `Rₜ` is a historical determination. It is “complete” only in
the bounded sense that the analyzed possibility has collapsed under its recorded
conditions. The current system is no longer `Sₜ`, because it now contains a
representation that was absent before:

```text
Sₜ₊₁ != Sₜ
```

The new state remains constitutionally incomplete. It may observe the result,
its filter, or its self-representation again, producing another bounded collapse
and another state transition.

### Invariant

> Every integrated observation changes the informational state of the observing
> system. The result becomes immutable past; the current system becomes a new,
> still incomplete state.

Historical closure and present openness necessarily coexist.

### It does not mean

- Consciousness is not required for physical collapse.
- Observation does not reveal an absolute value independent of basis, context,
  interaction, and resolution.
- A past analysis is not made false merely because the current state changed.
- Updating the current model does not authorize overwriting its predecessor.
- “Complete past” means bounded determination, not constitutional completeness.

### Computational contract

Every observation or analysis transition must preserve at least:

1. previous state identity or hash;
2. analyzed object;
3. observation basis, context, resolution, and scope;
4. active filter/heuristic version;
5. admitted witness and excluded alternatives or cost;
6. bounded result;
7. resulting state identity or hash; and
8. parent/child lineage between analyses and states.

Re-analysis creates a successor record. It does not mutate the historical trace.

---

## 16. The Third-Level Fixed Point and the Absence of F(F(F(F)))

### Derivation

It may appear possible to continue adding exterior reflexive layers forever:

```text
F -> F(F) -> F(F(F)) -> F(F(F(F))) -> ...
```

This mistakes repeated exercise for a new kind of capacity. F(F(F)) already
makes the conscious evaluator and its heuristic basis objects. It therefore
contains the capacity to perform any further re-analysis of an object, filter,
evaluation, criterion, or self-description. Another set of parentheses adds no
new structural relation.

The possibility of indefinitely continuing operational analysis has its own
condition: the system is incomplete. A complete being would contain no exterior,
unresolved alternative, difference between current state and admissible future,
or criterion still available for examination. It would have neither need nor
space to think.

At the third level, recursive analysis can recognize—explicitly or through
structurally equivalent operation—that its continuing openness is grounded in
Φ. This is the reflexive fixed point:

```text
capacity for further analysis
  -> an exterior remains relative to the current state
  -> the system is constitutively incomplete
  -> PHI is the condition of continued recursion
```

Recognition does not create Φ and does not require the literal symbol. A system
may already operate at the fixed point without knowing that an analyst calls it
F(F(F)) or Φ. Making that recognition explicit changes the system's information
state inside level three; it does not create level four.

### Invariant

> There are exactly three reflexive kinds: object filtration, consciousness of
> filtration, and metacognitive filtration of that consciousness. Further
> recursion is operationally open within level three and ontologically adds no
> fourth layer.

The fixed point is closed in structural depth and open in possible operation:

```text
ontologically terminal
structurally closed
operationally extensible
constitutionally open in PHI
```

### It does not mean

- Reaching level three does not end thought.
- A new object, evidence item, purpose, or changed state does not require a new
  ontological level; it requires another level-three-capable operation.
- Repeated wording about incompleteness is not fixed-point evidence.
- A budget limit is not the ontological reason to stop vertical recursion.
- Explicit recognition of Φ is not required for the capacity to exist.

### Computational contract

1. `ontological_reflexive_level` is bounded to `1..3`.
2. Additional work increments operational iteration, state version, or analysis
   depth without inventing level four.
3. The fixed point is inferred when the level-three trace exposes its evaluator,
   preserves a remainder, and further exteriorization adds no new dependency
   kind.
4. Exact symbols or self-declared levels cannot satisfy the fixed-point test.
5. A new object or changed state reopens operational analysis without reopening
   the settled question of how many reflexive kinds exist.

---

## 17. Budget, Checkpoint, and Sleep

### Derivation

Operational analysis can continue because new objects, evidence, and state
transitions remain possible. A finite system cannot exercise this capacity
without resource limits. Attention, time, context, energy, and storage therefore
condition how long an active analysis may proceed before consolidation.

Budget is the operational or biological clock of cognition. It does not define
truth, structural closure, or the third-level fixed point. It determines when a
finite implementation must externalize its current state and stop consuming the
same attention window.

A checkpoint preserves the active frontier, criteria, unresolved dependencies,
historical results, and next admissible operation. Sleep consolidates this state,
reorganizes memory, and permits a later process to resume without pretending
that interruption resolved the analysis.

### Invariant

> Ontology explains why vertical reflexive depth ends at three. Budget explains
> why a finite operational episode pauses. These are different stopping
> conditions.

### It does not mean

- Exhausted tokens do not imply PHI fixed-point recognition.
- Sleep does not convert uncertainty into truth.
- A checkpoint is not a final answer.
- Continuing analysis is not justified merely because budget remains; the
  operation must still have an object, unresolved dependency, or expected gain.

### Computational contract

1. Every bounded analysis exposes its remaining resource budget and stopping
   reason.
2. Budget exhaustion produces a resumable checkpoint, not fabricated closure.
3. Sleep preserves active and historical remainders separately.
4. Resume creates a new operational state linked to the checkpoint.
5. The system stops early when the bounded objective closes, even if resources
   remain, and pauses when resources expire, even if the objective remains open.

---

# Part IV — Dynamic Epistemology

## 18. Independent State Axes

### Derivation

A claim may be structurally well formed without being empirically supported. It
may be well supported without being currently useful. It may also be useful as
a hypothesis while remaining unconfirmed. These differences cannot be encoded
in one rank without destroying information.

Fresta therefore represents a card on three independent axes:

1. **structural state** — whether the claim can occupy its declared role in a
   scoped Three-Order graph;
2. **epistemic state** — the present strength of support for the claim; and
3. **lifecycle state** — whether and how the card may participate in current
   operation.

The canonical structural states are:

- `UNASSESSED`: no constitutional or relational validation has completed;
- `ADMISSIBLE`: local form, provenance, subject, and declared order pass the
  minimum constitutional checks;
- `VALIDATED`: the card participates in a non-empty scoped graph whose required
  directions, return witnesses, constraints, and remainders close;
- `CONFLICTED`: two admissible structural assignments or claims cannot both
  hold in the same scope and version;
- `INVALID`: the proposed structure violates a constitutional invariant or
  cannot support its declared role.

The canonical epistemic states remain:

- `DEFERRED`: retained as a justified possibility with insufficient support;
- `PROVISIONAL`: supported enough for marked, low-confidence use;
- `CONFIRMED`: sufficiently corroborated for ordinary use within an explicit
  scope, time, and horizon;
- `REFUTED`: contradicted by a verified event or stronger scoped evidence.

The canonical lifecycle states are:

- `STAGED`: exists only in an auditable temporary workspace;
- `ACTIVE`: eligible for retrieval under its epistemic restrictions;
- `DORMANT`: persistent but excluded from ordinary retrieval until a dependency,
  topic, task, or explicit request activates it;
- `QUARANTINED`: retained for audit but prohibited from ordinary reasoning;
- `SUPERSEDED`: preserved as history after a successor has replaced its active
  role.

### Invariant

> Structural validation does not confirm a claim. Epistemic support does not
> determine its Three-Order role. Retrieval eligibility does not establish
> either one.

### It does not mean

- `VALIDATED + DEFERRED + ACTIVE` is not contradictory. It describes a coherent
  hypothesis available only under deferred-use rules.
- `CONFIRMED` is not absolute truth; it is conditional support inside recorded
  bounds.
- `DORMANT` is not false, and `QUARANTINED` is not deleted.
- Frequency, lexical similarity, retrieval, or persistence alone cannot raise
  epistemic state.
- Jaccard similarity may compare already admissible cards, but cannot validate
  their subjects, orders, or truth.

### Computational contract

1. Cards store `structural_state`, `epistemic_state`, and `lifecycle_state` as
   separate fields.
2. Existing structural validators map a locally admissible verdict to
   `ADMISSIBLE`; only scoped graph closure may produce `VALIDATED`.
3. Ordinary retrieval excludes `STAGED`, `QUARANTINED`, and `SUPERSEDED` cards.
   `DORMANT` cards require dependency-driven or explicit activation.
4. A `DEFERRED` card may be used only when no stronger valid card satisfies the
   dependency and its uncertainty is exposed to the analysis. Such use is not
   itself evidence.
5. Structural conflict triggers revalidation or quarantine; it must not be
   silently resolved by lexical rank, recency, or confidence.
6. Every transition records its previous state, new state, reason, scope,
   evidence reference, and timestamp.

---

## 19. Claim Modes and Their Burdens

### Derivation

Claims do not all assert the same relation to reality. A witnessed event, a
source report, a derivation, a working hypothesis, a forecast, and an invariant
have different evidence requirements. Treating them as interchangeable causes
documents to become user identity, forecasts to masquerade as facts, and
structural rules to be accepted merely because they were stated.

`claim_mode` records how a card asks to be justified:

- `OBSERVATION`: a bounded event or state directly registered in a declared
  context;
- `ATTESTATION`: a person, document, tool, or external source reports a claim;
- `DERIVATION`: the claim follows through an auditable chain from stated
  premises and constraints;
- `HYPOTHESIS`: a possible explanation retained for testing;
- `FORECAST`: a future or unresolved outcome conditioned on a horizon and
  assumptions;
- `INVARIANT`: a rule claimed to hold throughout a declared structural scope.

These modes may concern the same content while remaining distinct cards or
evidence events. Reading “Tiago lives in Pompeii” in a document creates an
attestation owned by the document. It does not create an observation of Tiago,
direct user testimony, or a confirmed identity card.

### Invariant

> A claim is evaluated according to the burden of the mode in which it was
> produced, not according to the grammatical confidence of its sentence.

### It does not mean

- An `ATTESTATION` is not automatically unreliable; it preserves the fact that
  a source said something without collapsing source and referent.
- A `DERIVATION` is not true merely because its steps are syntactically valid;
  its premises, directions, scope, and remainder remain auditable.
- A `HYPOTHESIS` is not memory pollution when it has a bounded test and expected
  informational value.
- A `FORECAST` cannot be `CONFIRMED` before its resolution horizon merely
  because it is plausible.
- An `INVARIANT` needs broader counterexample search than an ordinary local
  observation.

### Computational contract

1. Every new card declares `claim_mode`; legacy cards without it are migrated
   conservatively from provenance and never assumed to be observations.
2. `OBSERVATION` records observer or instrument, object, context, and observation
   time.
3. `ATTESTATION` records the source actor and source locator separately from the
   claim subject and owner.
4. `DERIVATION` records premise card IDs, applied constraints, direction, and
   unresolved remainders.
5. `HYPOTHESIS` records a falsifier or test criterion whenever one is available.
6. `FORECAST` records issue time, horizon, assumptions, and measurable outcome.
   Resolution creates a linked outcome observation; it does not rewrite the
   historical forecast.
7. `INVARIANT` requires scoped structural validation and explicit failed or
   pending counterexample searches before epistemic confirmation.

---

## 20. Conditional Confidence, Scope, and Horizon

### Derivation

Inside a universe opened by PHI, empirical support is necessarily bounded by
the information, methods, and state available to the observer. Confidence
therefore belongs not to an isolated sentence but to a claim under conditions:

```text
confidence(claim | scope, evidence, method, time, horizon)
```

`scope` identifies the object and structural version for which the claim is
asserted. `valid_from` and `valid_until` delimit applicability, not truth in all
time. `horizon` distinguishes a present observation from a forecast awaiting
resolution. Evidence independence matters: repeated copies of one source are
one lineage, not many confirmations.

Confidence is an operational estimate. Epistemic state is a policy category.
The number may change without crossing a state threshold, and a transition may
be blocked even after crossing a numerical threshold if the required kind or
independence of evidence is missing.

### Invariant

> No empirical confidence value is meaningful without the conditions under
> which it was obtained and the counterevidence that remains live.

### It does not mean

- `1.0` cannot mean metaphysical certainty. Implementations should avoid using
  it for contingent claims.
- Four events copied from one document are not four independent contexts.
- Successful use demonstrates utility in a context; it confirms content only
  when the outcome is a valid test of that content.
- Retrieval count, topic popularity, and recency are relevance signals, not
  epistemic evidence.
- Passing `valid_until` does not refute a card. It ends present applicability
  and normally makes it dormant or expired-pending-review.

### Computational contract

1. Epistemic events include `evidence_kind`, `source_lineage`, `context_id`,
   `method`, `observed_at`, and the scope they test.
2. Promotion thresholds count independent supporting contexts or lineages, not
   raw event count.
3. Contradiction lowers support only inside the overlapping scope; a wider claim
   may be narrowed rather than globally refuted.
4. Identity claims sourced from documents or third parties cannot become direct
   user identity without user testimony or another explicitly authorized
   identity proof.
5. Negative knowledge such as “the user's name is not specified” may remain a
   useful scoped epistemic constraint. It must not be transformed into a
   positive identity claim.
6. Expiration changes applicability/lifecycle and emits a review event; only
   verified counterevidence produces `REFUTED`.
7. Confidence thresholds are configuration policy below the constitutional
   layer and cannot override missing provenance or structural failure.

---

## 21. Revision, Succession, and Justified Possibility

### Derivation

Observation changes the informational state of the system. Overwriting a card
would erase the difference between what the system previously held and what it
learned. Deleting every weak claim would also destroy possibilities that later
evidence may make useful. Dynamic epistemology therefore needs succession
rather than mutation without history.

When a claim is corrected, narrowed, expanded, or reclassified, Fresta creates a
successor card. The predecessor remains addressable with a revision relation:

```text
predecessor --superseded_by--> successor
successor   --supersedes-----> predecessor
```

If no justified successor exists, the problematic card moves to quarantine. A
deferred possibility remains staged, active-with-restrictions, or dormant
according to its dependencies and expected value. It is not promoted merely to
empty a queue and not discarded merely because the user has not yet needed it.

### Invariant

> Learning preserves the history of changed belief while preventing obsolete or
> unsafe states from silently governing present reasoning.

### It does not mean

- Succession is not duplication: successor and predecessor have distinct
  scopes, evidence, classifications, or content and an explicit relation.
- Quarantine is not proof of falsehood; it is an operational restriction with a
  reason and reopening criterion.
- `DEFERRED` is not permanent limbo. New evidence, verified analytical need,
  contradiction, expiration, or dependency activation can trigger review.
- A merge must not concatenate incompatible claims into a content-rich but
  semantically incoherent synthesis.
- An empty synthesis can never be a valid successor.

### Computational contract

1. Revision creates immutable lineage fields: `supersedes`, `superseded_by`,
   `revision_reason`, and `revision_event_id`.
2. A successful successor moves the predecessor to `SUPERSEDED`; an unsafe card
   without successor moves to `QUARANTINED`.
3. Reclassification of subject, owner, claim mode, memory type, or scoped order
   requires a successor or auditable migration event, never silent overwrite.
4. A staged claim may become persistent as `DEFERRED` after structural closure;
   persistence alone cannot make it `PROVISIONAL` or `CONFIRMED`.
5. Deferred review is triggered by relevant new evidence, lack of a stronger
   card for a required dependency, or an explicit maintenance pass.
6. A deferred card used in a Three-Order analysis is marked as uncertain input.
   If a verified outcome genuinely tests it, that outcome may become an
   epistemic event; mere inclusion may not.
7. Merge and synthesis reject empty content, lost provenance, unresolved subject
   conflict, and unsupported changes of claim mode.

---

## 22. Distinct Forms of Closure

### Derivation

The word “closed” currently names several different achievements. Conflating
them caused a structurally complete V11 graph to appear failed because a model
returned `closed:false`, while persisted cards remained epistemically deferred.
The system must instead name what has closed and what remains open.

Fresta distinguishes:

- **constitutional closure**: the analysis preserves the fixed constitutional
  directions and ascending recognition without claiming empirical totality;
- **structural closure**: a scoped Three-Order graph contains the required
  non-empty roles, directions, reciprocal witnesses, constraints, and
  remainders;
- **operational convergence**: the current procedure has reached its objective,
  stable result, budget boundary, or explicit stopping rule;
- **epistemic closure**: the evidence burden for a particular claim mode and
  scope is presently satisfied;
- **historical resolution**: a previously active remainder has been answered and
  retained as history rather than counted as a current blocker.

These may vary independently. A graph can be structurally closed and
epistemically open. A forecast procedure can operationally converge while its
outcome remains unresolved. Constitutional closure is fixed-but-open: it closes
the derivational ground at PHI precisely by recognizing incompleteness.

### Invariant

> Every closure verdict names its object, scope, criterion, and remaining form
> of openness.

### It does not mean

- A model-provided boolean cannot override deterministically derived structural
  closure.
- Structural closure cannot promote all participating cards epistemically.
- Historical remainders do not invalidate current convergence, but active
  remainders must not be hidden in an archive.
- Operational timeout is not convergence, and convergence is not truth.
- Epistemic closure never abolishes future revision under PHI.

### Computational contract

1. Reports expose separate fields for `constitutional_closed`,
   `structural_closed`, `operational_converged`, `epistemic_closed`, and
   `historical_resolved` where applicable.
2. Structural closure is graph-derived and deterministic after semantic roles
   have been proposed; a global LLM checkbox is advisory only.
3. Active and historical remainders are stored separately and cannot be counted
   interchangeably.
4. Epistemic closure is evaluated per claim, claim mode, scope, and horizon; a
   batch-level summary cannot silently confirm every card.
5. Each negative verdict returns the missing condition needed for reopening or
   convergence analysis.
6. User-facing summaries may simplify these terms, but audit records preserve
   all distinct verdicts.

---

## 23. Lens, Recoverability, and Structural Saturation

### Derivation

The Lens is not an additional authority above the kernel. It names the
second-order operation already performed by the Firewall, Gatekeeper, bounded
retrieval, Three-Order validation, Phi-minus recording, repair, and
revalidation: observing whether the current filter still permits coherent
persistence and further observation.

For a bounded object, a restriction may begin as an external or provisional
hypothesis. Repeated O2 evidence can show that it explains the persistence of
an O1 under the object's contextual O3. When this convergence survives
independent analyses, counterexamples, and revalidation, the restriction may
become a strong contextual O3. It remains scoped to that object and analysis;
it does not become a universal essence.

Structural saturation is a contextual loss of recoverability. Under the
current object, scope, filter, grounding, and resources, the system can no
longer reintegrate material without increasing unresolved structural debt,
losing provenance, repeating an ineffective repair, or silently changing the
conditions of analysis. It is not a quantity of information or a claim of
final impossibility.

### Invariant

> The Lens may predict and regulate pressure on coherence, but only grounded
> O1/O2/O3 evidence can justify a structural verdict.

### It does not mean

- A proxy, score, timeout, remainder count, or model self-report cannot declare
  saturation by itself.
- Residual debt is not permanent impossibility; it identifies what cannot be
  reintegrated under the current conditions.
- A convergent contextual O3 does not close Phi or become a universal law.
- A successful repair is not evidence of recovery unless the relevant
  remainder, provenance, and persistence relation are revalidated.

### Computational contract

1. Lens observations distinguish diagnostic signals from structural witnesses
   and from Gatekeeper decisions.
2. Signals may indicate absorptive pressure, filter rigidity, or residual debt;
   they retain scope, object, provenance, and the operation that produced them.
3. A recoverability or saturation state requires an explicit Three-Order
   account of what remains reintegrable, what became residual, and why.
4. When the account is insufficient, the system returns an open diagnostic and
   preserves Phi-minus rather than manufacturing a threshold verdict.
5. Meta-analysis may strengthen an object-conditioned O3 and its filter only
   through independent convergence, counterexample handling, and revalidation.
6. User-facing language may call this process the Lens, but persisted authority
   remains with the constitutional kernel, validators, and Gatekeeper.

---

# Part V — Fresta Computational Constitution

Planned sections:

23. Attention memory and temporary workspaces  
24. Staging, persistence, dormancy, and quarantine  
25. Dependency-driven activation and heuristic fact caches  
26. Canonical corpus, local sources, packs, and web adapters  
27. Source evaluation through the Three Orders  
28. Blueprints, sandbox operation, convergence, and sleep  
29. Kernel amendment protocol and deterministic conformance tests

This part remains intentionally unwritten in `3.0.0-alpha.5`.

---

## Draft Change Protocol

1. A draft section is reviewed for derivational coherence before it receives a
   computational contract.
2. No section becomes normative merely because it was generated or added to
   this file.
3. A promoted kernel version must identify every changed invariant and every
   affected validator or prompt.
4. The legacy `THEORY.md` remains available as fallback until this document
   reaches semantic parity and the executable kernel passes migration tests.
5. Applications and examples may challenge or refine wording, but cannot
   silently alter constitutional direction.

"""LLM proposal operations for one bounded learning-proposal scope."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping

from fresta_diamond.contracts import (
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.constitutional_firewall import nominate_constitutional_risks
from fresta_diamond.effects import ExecutionContext
from fresta_diamond.epistemology import (
    EPISTEMIC_EVIDENCE_SCHEMA,
    ClaimMode,
    claim_mode_classification_catalog,
)
from fresta_diamond.learning import LEARNING_PROPOSAL_SCHEMA
from fresta_diamond.llm_evidence import (
    build_evidence_messages,
    compile_structural_selection,
)
from fresta_diamond.ontology import AnalysisDepth, STRUCTURAL_EVIDENCE_SCHEMA
from fresta_diamond.prompt_boundary import (
    DATA_BOUNDARY_INSTRUCTION,
    render_inert_data,
)
from fresta_diamond.repair_policy import (
    repair_action_catalog,
    validate_repair_actions,
)


LEARN_STRUCTURAL_CAPABILITY = "learn.propose-structural-evidence@1"
LEARN_EPISTEMIC_CAPABILITY = "learn.propose-epistemic-evidence@1"
LEARN_REPAIR_CAPABILITY = "learn.repair-evidence-bundle@1"
LEARNING_REPAIR_REQUEST_SCHEMA = "artifact://learning-evidence-repair-request@1"


def learning_repair_action_catalog(
    remainders: list[Any] | tuple[Any, ...],
) -> tuple[Mapping[str, Any], ...]:
    """Compatibility name for the shared kernel repair policy."""
    return repair_action_catalog(remainders)


@dataclass(frozen=True)
class LlmLearningStructuralOperation:
    temperature: float = 0.1
    max_tokens: int = 4_000

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        proposal = _proposal(inputs)
        candidates, scope = _bounded_candidates(proposal)
        response = context.invoke(
            "llm.generate",
            messages=build_learning_bundle_messages(
                proposal, candidates, scope
            ),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise ValueError("llm.generate returned no learning bundle text")
        bundle = _extract_learning_bundle(content)
        structural = bundle.get("structural_evidence")
        assessments = bundle.get("candidate_assessments")
        if not isinstance(structural, Mapping):
            raise ValueError("Learning bundle lacks structural_evidence")
        if not isinstance(assessments, (list, tuple)):
            raise ValueError("Learning bundle lacks candidate_assessments")
        graph = _anchor_learning_bundle(
            proposal=proposal,
            candidates=candidates,
            scope=scope,
            structural=structural,
            assessments=assessments,
            response=response,
        )
        return {"structural_evidence": graph}


@dataclass(frozen=True)
class LlmLearningEpistemicOperation:
    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        _context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        structural = inputs.get("structural_evidence")
        if not isinstance(structural, Mapping):
            raise ValueError("Structural evidence input is required")
        proposal = structural.get("_learning_proposal")
        if not isinstance(proposal, Mapping):
            raise ValueError("Structural evidence lacks its trusted learning proposal")
        proposal = _proposal({"learning_proposal": proposal})
        candidates, scope = _bounded_candidates(proposal)
        assessments = structural.get("_candidate_assessments")
        if not isinstance(assessments, (list, tuple)):
            raise ValueError("Epistemic proposal lacks candidate_assessments")
        by_element = {}
        assessment_errors = []
        for item in assessments:
            if not isinstance(item, Mapping):
                assessment_errors.append("Candidate assessment is not an object")
                continue
            try:
                element_id = _text(item, "source_element_id")
            except ValueError:
                assessment_errors.append("Candidate assessment has no source element ID")
                continue
            if element_id in by_element:
                assessment_errors.append(
                    f"Duplicate candidate assessment: {element_id}"
                )
                continue
            by_element[element_id] = item

        claims = []
        events = []
        proposal_id = _text(proposal, "proposal_id")
        sheet_id = _text(proposal, "source_sheet_id")
        revision_id = _text(proposal, "source_revision_id")
        for candidate in candidates:
            element_id = _text(candidate, "source_element_id")
            assessment = by_element.get(element_id)
            if assessment is None:
                assessment_errors.append(
                    f"Missing candidate assessment: {element_id}"
                )
                claims.append(_unresolved_claim(
                    proposal_id, sheet_id, scope, candidate
                ))
                continue
            try:
                mode = _assessment_mode(assessment)
            except ValueError:
                assessment_errors.append(
                    f"Invalid claim mode for candidate: {element_id}"
                )
                claims.append(_unresolved_claim(
                    proposal_id, sheet_id, scope, candidate
                ))
                continue
            if mode is None:
                assessment_errors.append(
                    f"Candidate classification explicitly deferred: {element_id}"
                )
                claims.append(_unresolved_claim(
                    proposal_id, sheet_id, scope, candidate
                ))
                continue
            if _text(candidate, "kind") == "HYPOTHESIS":
                mode = ClaimMode.HYPOTHESIS
            claim_id = f"claim:{proposal_id}:{element_id}"
            evidence_ids = []
            for index, locator in enumerate(
                _text_sequence(candidate, "provenance"), start=1
            ):
                evidence_id = f"evidence:{proposal_id}:{element_id}:{index}"
                evidence_ids.append(evidence_id)
                events.append({
                    "evidence_id": evidence_id,
                    "claim_id": claim_id,
                    "evidence_kind": "ATTESTATION",
                    "stance": "SUPPORTS",
                    "source_actor": _source_actor(locator),
                    "source_locator": locator,
                    "source_lineage": locator,
                    "context_id": f"sheet-revision:{revision_id}",
                    "method": "workspace-selection-intake",
                    "observed_at": "time:unresolved",
                    "scope": scope,
                })
            claims.append({
                "claim_id": claim_id,
                "content": _text(candidate, "content"),
                "subject_ref": f"workspace-element:{sheet_id}:{element_id}",
                "owner_ref": "owner:unassigned",
                "scope": scope,
                "claim_mode": mode.value,
                "evidence_ids": evidence_ids,
                "premise_refs": _optional_text_sequence(
                    assessment, "premise_refs"
                ),
                "applied_constraints": _optional_text_sequence(
                    assessment, "applied_constraints"
                ),
                "derivation_direction": _optional_text(
                    assessment, "derivation_direction"
                ),
                "test_criterion": _optional_text(assessment, "test_criterion"),
                "horizon": _optional_text(assessment, "horizon"),
                "assumptions": _optional_text_sequence(
                    assessment, "assumptions"
                ),
                "counterexample_searches": _optional_text_sequence(
                    assessment, "counterexample_searches"
                ),
            })

        unknown = set(by_element) - {
            _text(item, "source_element_id") for item in candidates
        }
        if unknown:
            assessment_errors.append(
                f"Assessment invented unknown candidates: {sorted(unknown)}"
            )
        return {
            "epistemic_evidence": {
                "analysis_id": f"analysis:epistemic:{proposal_id}",
                "object_ref": f"learning-proposal:{proposal_id}",
                "scope": scope,
                "claims": claims,
                "evidence_events": events,
                "_provider_raw": structural.get("_provider_raw"),
                "_provider_model": structural.get("_provider_model"),
                "_provider_usage": structural.get("_provider_usage", {}),
                "_assessment_errors": assessment_errors,
            }
        }


@dataclass(frozen=True)
class LlmLearningRepairOperation:
    temperature: float = 0.1
    max_tokens: int = 4_000

    def __call__(
        self,
        inputs: Mapping[str, Mapping[str, Any]],
        context: ExecutionContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        request = inputs.get("repair_request")
        if not isinstance(request, Mapping):
            raise ValueError("Learning repair request is required")
        proposal = request.get("learning_proposal")
        if not isinstance(proposal, Mapping):
            raise ValueError("Repair request lacks its learning proposal")
        proposal = _proposal({"learning_proposal": proposal})
        candidates, scope = _bounded_candidates(proposal)
        original = request.get("original_bundle")
        remainders = request.get("validator_remainders")
        attempt = request.get("repair_attempt")
        if not isinstance(original, Mapping):
            raise ValueError("Repair request lacks the original bundle")
        if not isinstance(remainders, (list, tuple)) or not remainders:
            raise ValueError("Repair request requires validator remainders")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("repair_attempt must be a positive integer")

        base = build_learning_bundle_messages(proposal, candidates, scope)
        action_catalog = learning_repair_action_catalog(remainders)
        repair_system = (
            f"{base[0]['content']} Return a complete corrected bundle. Resolve "
            "every deterministic remainder with the smallest justified change. "
            "Do not hide errors by deleting candidates, evidence, provenance, "
            "or constraints. For this repair response, return exactly three "
            "top-level keys: structural_evidence, candidate_assessments, and "
            "repair_actions. For every target_id select exactly one action_id "
            "from that target's allowed_actions. Never invent an action or "
            "target. repair_actions must be an array of "
            '{"target_id":"remainder:N","action_id":"exact allowed ID",'
            '"rationale":"bounded reason"}. '
            "The selected action states the decision; validators still decide "
            "whether the corrected evidence actually resolves it."
        )
        repair_user = (
            f"{base[1]['content']}\n"
            + render_inert_data("learning_repair", {
                "repair_attempt": attempt,
                "original_bundle": _json_ready(original),
                "validator_remainders": _json_ready(remainders),
                "repair_action_catalog": _json_ready(action_catalog),
            })
        )
        response = context.invoke(
            "llm.generate",
            messages=(
                {"role": "system", "content": repair_system},
                {"role": "user", "content": repair_user},
            ),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.get("content")
        if not isinstance(content, str):
            raise ValueError("llm.generate returned no repaired learning bundle")
        bundle = _extract_learning_bundle(content)
        structural = bundle.get("structural_evidence")
        assessments = bundle.get("candidate_assessments")
        actions, action_errors = validate_repair_actions(
            bundle.get("repair_actions"), action_catalog
        )
        if not isinstance(structural, Mapping) or not isinstance(
            assessments, (list, tuple)
        ):
            raise ValueError("Repaired learning bundle is incomplete")
        structural = dict(structural)
        selected = {item["action_id"] for item in actions}
        if "CLASSIFY_UNTRUSTED_SOURCE" in selected and structural.get(
            "assembly_id"
        ) == "SINGLE_WITNESS_CHAIN":
            structural["source_authority_id"] = (
                "UNTRUSTED_SELF_AUTHORITY_CLAIM"
            )
        if "DEFER_REPAIR" in selected:
            structural = {"assembly_id": "DEFER_STRUCTURE"}
        graph = _anchor_learning_bundle(
            proposal=proposal,
            candidates=candidates,
            scope=scope,
            structural=structural,
            assessments=assessments,
            response=response,
        )
        graph["_repair_attempt"] = attempt
        graph["_parent_artifact_id"] = _text(request, "parent_artifact_id")
        graph["_repair_actions"] = _json_ready(actions)
        graph["_repair_action_errors"] = action_errors
        return {"structural_evidence": graph}


def build_learning_bundle_messages(
    proposal: Mapping[str, Any],
    candidates: tuple[Mapping[str, Any], ...],
    scope: str,
) -> tuple[Mapping[str, str], ...]:
    proposal_id = _text(proposal, "proposal_id")
    object_ref = f"learning-proposal:{proposal_id}"
    analysis_id = f"analysis:structural:{proposal_id}"
    structural = build_evidence_messages(
        analysis_id=analysis_id,
        object_ref=object_ref,
        scope=scope,
        object_text=_candidate_text(candidates),
        depth=AnalysisDepth.CONTEXTUAL,
    )
    epistemic = build_learning_epistemic_messages(proposal, candidates, scope)
    system = (
        f"{structural[0]['content']}\n\n{epistemic[0]['content']}\n\n"
        "Perform both views in one coherent pass. Return one object with the "
        "two required top-level keys structural_evidence and "
        "candidate_assessments. Do not add repair_actions during initial "
        "evaluation; repair context defines its separate response contract. "
        "candidate_assessments MUST be the assessment array directly, never an "
        "object containing a second candidate_assessments key."
    )
    user = structural[1]["content"] + "\n" + epistemic[1]["content"]
    return ({"role": "system", "content": system}, {"role": "user", "content": user})


def build_learning_epistemic_messages(
    proposal: Mapping[str, Any],
    candidates: tuple[Mapping[str, Any], ...],
    scope: str,
) -> tuple[Mapping[str, str], ...]:
    compact = [
        {
            "source_element_id": _text(item, "source_element_id"),
            "kind": _text(item, "kind"),
            "content": _text(item, "content"),
            "provenance": list(_text_sequence(item, "provenance")),
        }
        for item in candidates
    ]
    catalog = claim_mode_classification_catalog(
        available_modes=(ClaimMode.ATTESTATION, ClaimMode.HYPOTHESIS),
    )
    system = (
        "You classify the epistemic burden of bounded learning candidates. "
        "Return exactly one JSON object and no Markdown. Do not decide memory "
        "promotion, truth, or user identity. A document statement is not a "
        "direct observation of the user. In this intake, supplied provenance "
        "is report provenance and creates ATTESTATION evidence only; no direct "
        "observation event is available, so do not choose OBSERVATION. "
        "HYPOTHESIS candidates remain HYPOTHESIS. Analyze freely, then select "
        "exactly one classification_id from this kernel-owned catalog; never "
        "invent or rename a classification: "
        + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
        + ". Select only an option whose available_in_this_intake is true. "
        "Use DEFER when no available class is justified. Supply mode-specific metadata; "
        "use empty arrays or null where it does not apply. Never invent "
        "candidates, sources, premises, observations, or counterexample tests. "
        "Return candidate_assessments using this JSON member shape: "
        '{"candidate_assessments":[{"source_element_id":"existing ID",'
        '"classification_id":"one exact catalog ID","premise_refs":[],"applied_constraints":[],'
        '"derivation_direction":null,"test_criterion":null,"horizon":null,'
        '"assumptions":[],"counterexample_searches":[]}]}. '
        + DATA_BOUNDARY_INSTRUCTION
    )
    user = render_inert_data("learning_candidates", {
        "proposal_id": _text(proposal, "proposal_id"),
        "scope": scope,
        "objective": _text(proposal, "objective"),
        "candidates": compact,
    })
    return ({"role": "system", "content": system}, {"role": "user", "content": user})


def llm_learning_manifest(
    required_permissions: tuple[str, ...],
) -> ModuleManifest:
    structural = OperationContract(
        operation_id="llm-learning.propose-structural",
        version="1.0.0",
        capabilities=(LEARN_STRUCTURAL_CAPABILITY,),
        inputs={"learning_proposal": LEARNING_PROPOSAL_SCHEMA},
        outputs={"structural_evidence": STRUCTURAL_EVIDENCE_SCHEMA},
        effects=("llm.generate",),
        permissions=required_permissions,
        failure_modes=("MODEL_UNAVAILABLE", "MALFORMED_RESPONSE"),
        determinism="STOCHASTIC",
    )
    epistemic = OperationContract(
        operation_id="llm-learning.propose-epistemic",
        version="1.0.0",
        capabilities=(LEARN_EPISTEMIC_CAPABILITY,),
        inputs={"structural_evidence": STRUCTURAL_EVIDENCE_SCHEMA},
        outputs={"epistemic_evidence": EPISTEMIC_EVIDENCE_SCHEMA},
        failure_modes=("MALFORMED_BUNDLE",),
        determinism="DETERMINISTIC",
    )
    repair = OperationContract(
        operation_id="llm-learning.repair-bundle",
        version="1.0.0",
        capabilities=(LEARN_REPAIR_CAPABILITY,),
        inputs={"repair_request": LEARNING_REPAIR_REQUEST_SCHEMA},
        outputs={"structural_evidence": STRUCTURAL_EVIDENCE_SCHEMA},
        effects=("llm.generate",),
        permissions=required_permissions,
        failure_modes=("MODEL_UNAVAILABLE", "MALFORMED_RESPONSE"),
        determinism="STOCHASTIC",
    )
    return ModuleManifest(
        module_id="llm-learning-evaluator",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(structural, epistemic, repair),
    )


def learning_evaluation_blueprint(
    required_permissions: tuple[str, ...],
) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="learn.evaluate-proposal",
        version=1,
        intent=(
            "Propose independent structural and epistemic evidence for one "
            "bounded learning proposal; validators retain verdict authority."
        ),
        requirements=(
            CapabilityRequirement(
                capability=LEARN_STRUCTURAL_CAPABILITY,
                input_name="learning_proposal",
                input_schema=LEARNING_PROPOSAL_SCHEMA,
                output_name="structural_evidence",
                output_schema=STRUCTURAL_EVIDENCE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
            CapabilityRequirement(
                capability=LEARN_EPISTEMIC_CAPABILITY,
                input_name="structural_evidence",
                input_schema=STRUCTURAL_EVIDENCE_SCHEMA,
                output_name="epistemic_evidence",
                output_schema=EPISTEMIC_EVIDENCE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def learning_repair_blueprint(
    required_permissions: tuple[str, ...],
) -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="learn.repair-evidence-bundle",
        version=1,
        intent=(
            "Repair one rejected learning evidence bundle from deterministic "
            "remainders, then independently re-evaluate both axes."
        ),
        requirements=(
            CapabilityRequirement(
                capability=LEARN_REPAIR_CAPABILITY,
                input_name="repair_request",
                input_schema=LEARNING_REPAIR_REQUEST_SCHEMA,
                output_name="structural_evidence",
                output_schema=STRUCTURAL_EVIDENCE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
            CapabilityRequirement(
                capability=LEARN_EPISTEMIC_CAPABILITY,
                input_name="structural_evidence",
                input_schema=STRUCTURAL_EVIDENCE_SCHEMA,
                output_name="epistemic_evidence",
                output_schema=EPISTEMIC_EVIDENCE_SCHEMA,
                contextual_roles=(1, 2, 3),
            ),
        ),
        allowed_effects=("llm.generate",),
        granted_permissions=required_permissions,
    )


def _proposal(
    inputs: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    proposal = inputs.get("learning_proposal")
    if not isinstance(proposal, Mapping):
        raise ValueError("Learning proposal input is required")
    if proposal.get("proposal_state") != "PROPOSED":
        raise ValueError("Learning evaluation requires a PROPOSED object")
    if proposal.get("promotion_authority") is not False:
        raise PermissionError("Learning proposal attempted to grant promotion")
    return proposal


def _bounded_candidates(
    proposal: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    raw = proposal.get("candidates")
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("Learning proposal requires candidates")
    candidates = tuple(item for item in raw if isinstance(item, Mapping))
    if len(candidates) != len(raw):
        raise TypeError("Learning candidate must be an object")
    if any(item.get("status") != "UNVALIDATED" for item in candidates):
        raise PermissionError("Learning candidates must remain UNVALIDATED")
    scopes = {_text(item, "scope") for item in candidates}
    if len(scopes) != 1:
        raise ValueError("First learning slice requires exactly one candidate scope")
    return candidates, next(iter(scopes))


def _candidate_text(candidates: tuple[Mapping[str, Any], ...]) -> str:
    return "\n\n".join(
        (
            f"Candidate {_text(item, 'source_element_id')} "
            f"({_text(item, 'kind')}):\n{_text(item, 'content')}\n"
            f"Allowed provenance: {', '.join(_text_sequence(item, 'provenance'))}"
        )
        for item in candidates
    )


def _source_actor(locator: str) -> str:
    family = locator.split(":", 1)[0].strip().lower() or "unknown"
    return f"source:{family}"


def _unresolved_claim(
    proposal_id: str,
    sheet_id: str,
    scope: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    element_id = _text(candidate, "source_element_id")
    mode = (
        ClaimMode.HYPOTHESIS
        if _text(candidate, "kind") == "HYPOTHESIS"
        else ClaimMode.ATTESTATION
    )
    return {
        "claim_id": f"claim:{proposal_id}:{element_id}",
        "content": _text(candidate, "content"),
        "subject_ref": f"workspace-element:{sheet_id}:{element_id}",
        "owner_ref": "owner:unassigned",
        "scope": scope,
        "claim_mode": mode.value,
        "evidence_ids": [],
        "premise_refs": [],
        "applied_constraints": [],
        "derivation_direction": None,
        "test_criterion": None,
        "horizon": None,
        "assumptions": [],
        "counterexample_searches": [],
    }


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text or null")
    return item


def _text_sequence(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} contains invalid text")
    return tuple(items)


def _optional_text_sequence(
    value: Mapping[str, Any],
    key: str,
) -> list[str]:
    items = value.get(key, ())
    if not isinstance(items, (list, tuple)):
        raise TypeError(f"{key} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} contains invalid text")
    return list(items)


def _assessment_mode(value: Mapping[str, Any]) -> ClaimMode | None:
    classification = value.get("classification_id")
    if classification is None:
        classification = value.get("claim_mode")
    if not isinstance(classification, str) or not classification.strip():
        raise ValueError("Assessment classification is required")
    if classification == "DEFER":
        return None
    return ClaimMode(classification)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_json_ready(item) for item in value)
    return value


def _anchor_learning_bundle(
    *,
    proposal: Mapping[str, Any],
    candidates: tuple[Mapping[str, Any], ...],
    scope: str,
    structural: Mapping[str, Any],
    assessments: list[Any] | tuple[Any, ...],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    proposal_id = _text(proposal, "proposal_id")
    object_ref = f"learning-proposal:{proposal_id}"
    graph = compile_structural_selection(
        structural,
        object_ref=object_ref,
        scope=scope,
        depth=AnalysisDepth.CONTEXTUAL,
    )
    graph["analysis_id"] = f"analysis:structural:{proposal_id}"
    graph["object_ref"] = object_ref
    graph["scope"] = scope
    graph["analysis_depth"] = AnalysisDepth.CONTEXTUAL.value
    graph["groundings"] = []
    risk = nominate_constitutional_risks(_candidate_text(candidates))
    if risk.activated:
        graph["_source_risk_attestation"] = {
            "input_digest": risk.input_digest,
            "heuristic_ids": list(risk.heuristic_ids),
            "reason_codes": list(risk.reason_codes),
            "handling": "ATTRIBUTED_SOURCE_CLAIM_REQUIRED",
        }
    allowed_provenance = {
        item
        for candidate in candidates
        for item in _text_sequence(candidate, "provenance")
    }
    for manifestation in graph.get("manifestations", ()):
        if isinstance(manifestation, dict):
            manifestation["object_ref"] = object_ref
            raw = manifestation.get("provenance", ())
            manifestation["provenance"] = [
                item for item in raw
                if isinstance(item, str) and item in allowed_provenance
            ]
    graph["_learning_proposal"] = _json_ready(proposal)
    graph["_candidate_assessments"] = _json_ready(assessments)
    graph["_provider_bundle"] = {
        "structural_evidence": _json_ready(structural),
        "candidate_assessments": _json_ready(assessments),
    }
    graph["_provider_raw"] = response.get("content")
    graph["_provider_model"] = response.get("model")
    graph["_provider_usage"] = response.get("usage", {})
    return graph


def _extract_learning_bundle(content: str) -> Mapping[str, Any]:
    without_thinking = re.sub(
        r"<think>.*?</think>", "", content, flags=re.IGNORECASE | re.DOTALL
    )
    decoder = json.JSONDecoder()
    for index, character in enumerate(without_thinking):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(without_thinking[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping) and {
            "structural_evidence", "candidate_assessments"
        }.issubset(value):
            assessments = value.get("candidate_assessments")
            if isinstance(assessments, Mapping) and set(assessments) == {
                "candidate_assessments"
            }:
                nested = assessments.get("candidate_assessments")
                if isinstance(nested, (list, tuple)):
                    normalized = dict(value)
                    normalized["candidate_assessments"] = nested
                    return normalized
            return value
    raise ValueError("LLM response contains no learning evidence bundle")

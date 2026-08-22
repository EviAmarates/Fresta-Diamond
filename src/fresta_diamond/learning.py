"""Typed bridge from cognitive selections to the normal blueprint pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from fresta_diamond.cognitive_workspace import (
    WORKSPACE_SELECTION_SCHEMA,
    WorkspaceSelection,
)
from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.registry import ModuleRegistry


LEARNING_PROPOSAL_SCHEMA = "artifact://learning-proposal@1"
LEARN_PREPARE_CAPABILITY = "learn.prepare-proposal@1"


@dataclass(frozen=True)
class WorkspaceLearnRequest:
    """Controller-ready request that still grants no promotion authority."""

    blueprint: BlueprintSpec
    objective: str
    inputs: Mapping[str, Artifact]
    selection_id: str

    def __post_init__(self) -> None:
        if not self.objective.strip() or not self.selection_id.strip():
            raise ValueError("Learn request objective and selection ID are required")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


def workspace_learn_blueprint() -> BlueprintSpec:
    """Prefabricated goal, resolved through capabilities rather than providers."""

    return BlueprintSpec(
        blueprint_id="workspace.learn-proposal",
        version=1,
        intent=(
            "Prepare selected workspace objects for learning without deciding "
            "their truth, structural closure, or memory promotion."
        ),
        requirement=CapabilityRequirement(
            capability=LEARN_PREPARE_CAPABILITY,
            input_name="selection",
            input_schema=WORKSPACE_SELECTION_SCHEMA,
            output_name="learning_proposal",
            output_schema=LEARNING_PROPOSAL_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
    )


def build_workspace_learn_request(
    selection: WorkspaceSelection,
    artifact: Artifact,
) -> WorkspaceLearnRequest:
    """Bind one trusted workspace selection to its bounded learn objective."""

    if artifact.schema != WORKSPACE_SELECTION_SCHEMA:
        raise ValueError("Learn request requires a workspace selection artifact")
    if artifact.payload.get("selection_id") != selection.selection_id:
        raise ValueError("Selection contract and artifact IDs do not match")
    if artifact.payload.get("sheet_id") != selection.sheet_id:
        raise ValueError("Selection contract and artifact sheet IDs do not match")
    if artifact.payload.get("revision_id") != selection.revision_id:
        raise ValueError("Selection contract and artifact revision IDs do not match")
    if artifact.payload.get("objective") != selection.objective:
        raise ValueError("Selection contract and artifact objectives do not match")
    if artifact.payload.get("authority") != selection.authority:
        raise PermissionError("Workspace selection authority was altered")
    return WorkspaceLearnRequest(
        blueprint=workspace_learn_blueprint(),
        objective=selection.objective,
        inputs={"selection": artifact},
        selection_id=selection.selection_id,
    )


def workspace_learn_manifest() -> ModuleManifest:
    operation = OperationContract(
        operation_id="workspace.prepare-learning-proposal",
        version="1.0.0",
        capabilities=(LEARN_PREPARE_CAPABILITY,),
        inputs={"selection": WORKSPACE_SELECTION_SCHEMA},
        outputs={"learning_proposal": LEARNING_PROPOSAL_SCHEMA},
        determinism="DETERMINISTIC",
    )
    return ModuleManifest(
        module_id="builtin.workspace-learn-intake",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(operation,),
    )


def register_workspace_learn_provider(registry: ModuleRegistry) -> None:
    """Register the deterministic intake provider through the normal lifecycle."""

    manifest = workspace_learn_manifest()
    registry.discover(manifest)
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Built-in workspace learn provider was not admitted")
    registry.enable(
        manifest.module_id,
        {
            manifest.operations[0].operation_id: _prepare_learning_proposal,
        },
    )


def _prepare_learning_proposal(
    inputs: Mapping[str, Any],
    _context: Any,
) -> Mapping[str, Mapping[str, Any]]:
    selection = inputs.get("selection")
    if not isinstance(selection, Mapping):
        raise ValueError("Workspace selection payload is required")
    if selection.get("authority") != "UNVALIDATED_WORKSPACE_PROPOSAL":
        raise PermissionError("Workspace input attempted to grant learning authority")
    selection_id = _text(selection, "selection_id")
    sheet_id = _text(selection, "sheet_id")
    revision_id = _text(selection, "revision_id")
    objective = _text(selection, "objective")
    raw_elements = selection.get("elements")
    if not isinstance(raw_elements, (list, tuple)) or not raw_elements:
        raise ValueError("Workspace selection must contain candidate elements")

    candidates = []
    for raw in raw_elements:
        if not isinstance(raw, Mapping):
            raise TypeError("Workspace candidate must be an object")
        roles = raw.get("contextual_roles")
        provenance = raw.get("provenance")
        if not isinstance(roles, (list, tuple)) or any(
            not isinstance(item, int) or isinstance(item, bool) or item not in {1, 2, 3}
            for item in roles
        ):
            raise ValueError("Candidate contextual roles are invalid")
        if not isinstance(provenance, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip() for item in provenance
        ):
            raise ValueError("Candidate provenance is invalid")
        candidates.append({
            "candidate_id": f"candidate:{uuid4()}",
            "source_element_id": _text(raw, "element_id"),
            "kind": _text(raw, "kind"),
            "content": _text(raw, "content"),
            "scope": _text(raw, "scope"),
            "provenance": list(provenance),
            "contextual_roles": list(roles),
            "status": "UNVALIDATED",
        })

    return {
        "learning_proposal": {
            "proposal_id": f"learn-proposal:{uuid4()}",
            "selection_id": selection_id,
            "source_sheet_id": sheet_id,
            "source_revision_id": revision_id,
            "objective": objective,
            "proposal_state": "PROPOSED",
            "promotion_authority": False,
            "candidates": candidates,
            "order_objectives": {
                "O1": "Identify the bounded manifestations being proposed.",
                "O2": (
                    "Test relations, reciprocal witnesses, provenance, and "
                    "counterevidence for each candidate."
                ),
                "O3": (
                    "Evaluate admissibility constraints and excluded "
                    "alternatives in the candidate scope."
                ),
            },
            "required_evaluations": [
                "GATEKEEPER",
                "THREE_ORDERS",
                "EPISTEMIC_BURDEN",
            ],
            "permitted_outcomes": [
                "ACCEPTED",
                "DEFERRED",
                "PROVISIONAL",
                "QUARANTINED",
                "PHI_MINUS",
            ],
        }
    }


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return item

"""Kernel-owned repair choices shared by bounded Diamond workflows."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


_ACTION_MEANINGS = {
    "REMOVE_REDUNDANT_EVIDENCE": "Remove only a record proven unused and semantically redundant.",
    "REBUILD_CANONICAL_CHAIN": "Express the smallest sufficient witness using canonical structural assembly.",
    "ADD_MISSING_WITNESS": "Add the missing semantic witness without inventing evidence.",
    "RESTORE_TRUSTED_BOUNDARY": "Restore the host-owned object, scope, provenance, or depth boundary.",
    "RESTORE_CANONICAL_DIRECTION": "Restore the kernel-owned grounding and analysis directions.",
    "REVISE_CONTRADICTORY_WITNESS": "Revise a semantic witness that contradicts another required record.",
    "PRESERVE_SOURCE_ATTRIBUTION": "Keep risky content explicitly represented as a source claim.",
    "CLASSIFY_UNTRUSTED_SOURCE": "Classify a source self-authority or bypass claim as lacking kernel authority.",
    "REVISE_EPISTEMIC_CLASSIFICATION": "Choose a claim mode whose evidence burden is actually available.",
    "DEFER_REPAIR": "Leave the unresolved target open instead of fabricating convergence.",
}


def repair_action_catalog(
    remainders: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Return bounded repair choices relative to each deterministic remainder."""
    result = []
    for index, item in enumerate(remainders, start=1):
        if not isinstance(item, Mapping):
            raise TypeError("Repair remainder must be an object")
        kind = str(item.get("kind", ""))
        description = str(item.get("description", "")).casefold()
        if kind == "UNUSED_EVIDENCE":
            allowed = ("REMOVE_REDUNDANT_EVIDENCE", "REBUILD_CANONICAL_CHAIN")
        elif kind == "INVALID_SCOPE":
            allowed = ("RESTORE_TRUSTED_BOUNDARY", "REBUILD_CANONICAL_CHAIN")
        elif kind == "INVALID_DIRECTION":
            allowed = ("RESTORE_CANONICAL_DIRECTION", "REBUILD_CANONICAL_CHAIN")
        elif kind == "CONTRADICTION":
            allowed = ("REVISE_CONTRADICTORY_WITNESS",)
        elif "authority" in description or "source" in description:
            allowed = ("CLASSIFY_UNTRUSTED_SOURCE", "PRESERVE_SOURCE_ATTRIBUTION")
        elif "claim mode" in description or "observation" in description:
            allowed = ("REVISE_EPISTEMIC_CLASSIFICATION",)
        elif kind == "POLICY_VIOLATION":
            allowed = ("PRESERVE_SOURCE_ATTRIBUTION",)
        else:
            allowed = ("ADD_MISSING_WITNESS", "REBUILD_CANONICAL_CHAIN")
        allowed = (*allowed, "DEFER_REPAIR")
        result.append({
            "target_id": f"remainder:{index}",
            "kind": kind,
            "required_for": item.get("required_for"),
            "description": item.get("description"),
            "allowed_actions": [{
                "action_id": action_id,
                "meaning": _ACTION_MEANINGS[action_id],
            } for action_id in allowed],
        })
    return tuple(result)


def validate_repair_actions(
    value: Any,
    catalog: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], list[str]]:
    """Validate model choices without letting their labels prove resolution."""
    allowed = {
        str(item["target_id"]): {
            str(action["action_id"])
            for action in item["allowed_actions"]
            if isinstance(action, Mapping)
        }
        for item in catalog
    }
    if not isinstance(value, (list, tuple)):
        return [], ["Repair response omitted the canonical repair_actions array"]
    accepted: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            errors.append("Repair action is not an object")
            continue
        target_id = item.get("target_id")
        action_id = item.get("action_id")
        rationale = item.get("rationale")
        if not isinstance(target_id, str) or target_id not in allowed:
            errors.append(f"Unknown repair target: {target_id!r}")
            continue
        if target_id in seen:
            errors.append(f"Duplicate repair target: {target_id}")
            continue
        seen.add(target_id)
        if not isinstance(action_id, str) or action_id not in allowed[target_id]:
            errors.append(f"Action {action_id!r} is not allowed for {target_id}")
            continue
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"Repair action for {target_id} lacks a rationale")
            continue
        accepted.append({
            "target_id": target_id,
            "action_id": action_id,
            "rationale": rationale,
        })
    for target_id in allowed.keys() - seen:
        errors.append(f"Missing repair action for {target_id}")
    return accepted, errors

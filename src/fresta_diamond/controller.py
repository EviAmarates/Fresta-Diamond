"""Thin dependency-injected controller for the Diamond core."""

from __future__ import annotations

from dataclasses import replace
from collections.abc import Callable, Mapping

from fresta_diamond.contracts import Artifact, BlueprintSpec, ControllerResult
from fresta_diamond.constitutional_firewall import (
    ConstitutionalFirewall,
    FirewallAttestation,
    FirewallDecision,
    FirewallInterventionError,
    FirewallMode,
)
from fresta_diamond.engine import PlanValidator, Resolver, Runtime
from fresta_diamond.epistemology import EpistemicEvaluator
from fresta_diamond.effects import EffectBroker
from fresta_diamond.journal import (
    EventJournal,
    JournalArchive,
    JournalArchiveError,
    JournalEventKind,
)
from fresta_diamond.ontology import OntologyEvaluator
from fresta_diamond.registry import ModuleRegistry
from fresta_diamond.workspace import (
    CheckpointStore,
    CheckpointStoreError,
    ExecutionBudget,
    RuntimeCheckpoint,
)


_DEFAULT_FIREWALL = object()


class DiamondController:
    """Coordinate resolution and execution without knowing concrete providers."""

    def __init__(
        self,
        registry: ModuleRegistry,
        *,
        resolver: Resolver | None = None,
        validator: PlanValidator | None = None,
        runtime: Runtime | None = None,
        effect_broker: EffectBroker | None = None,
        ontology_evaluator: OntologyEvaluator | None = None,
        epistemic_evaluator: EpistemicEvaluator | None = None,
        journal: EventJournal | None = None,
        journal_archive: JournalArchive | None = None,
        checkpoint_store: CheckpointStore | None = None,
        firewall_escalation_handler: Callable[[FirewallAttestation, str], None]
        | None = None,
        firewall: ConstitutionalFirewall | None | object = _DEFAULT_FIREWALL,
    ) -> None:
        self._registry = registry
        self._resolver = resolver or Resolver()
        self._validator = validator or PlanValidator()
        self._runtime = runtime or Runtime()
        self._effect_broker = effect_broker or EffectBroker()
        self._ontology_evaluator = ontology_evaluator or OntologyEvaluator()
        self._epistemic_evaluator = epistemic_evaluator or EpistemicEvaluator()
        self._journal = journal
        if journal_archive is not None and journal is None:
            raise ValueError("Journal archive requires an injected EventJournal")
        self._journal_archive = journal_archive
        if checkpoint_store is not None and journal_archive is None:
            raise ValueError(
                "Checkpoint persistence requires an injected journal archive"
            )
        self._checkpoint_store = checkpoint_store
        self._firewall_escalation_handler = firewall_escalation_handler
        if firewall is _DEFAULT_FIREWALL:
            firewall = ConstitutionalFirewall()
        if firewall is None:
            raise RuntimeError(
                "DiamondController cannot exist without the constitutional firewall"
            )
        if not isinstance(firewall, ConstitutionalFirewall):
            raise TypeError("Invalid constitutional firewall binding")
        self._firewall = firewall

    def execute(
        self,
        blueprint: BlueprintSpec,
        objective: str,
        inputs: Mapping[str, Artifact],
        *,
        budget: ExecutionBudget | None = None,
    ) -> ControllerResult:
        journal_position = self._journal.position if self._journal is not None else 0
        firewall_attestation = self._firewall.open_analysis(objective)
        if not firewall_attestation.allows_execution:
            self._record_firewall(
                firewall_attestation.analysis_id,
                firewall_attestation,
            )
            self._escalate_firewall(firewall_attestation, objective)
            raise FirewallInterventionError(firewall_attestation)
        proposed = self._resolver.resolve(blueprint, objective, inputs, self._registry)
        cause = self._record_firewall(proposed.plan_id, firewall_attestation)
        cause = self._record(
            JournalEventKind.PLAN_PROPOSED,
            proposed.plan_id,
            proposed.plan_id,
            {
                "blueprint_id": proposed.blueprint_id,
                "blueprint_version": proposed.blueprint_version,
                "node_ids": tuple(node.node_id for node in proposed.nodes),
                "remainder_ids": tuple(
                    item.remainder_id for item in proposed.remainders
                ),
            },
            causation_id=cause,
        )
        validated = self._validator.validate(proposed, blueprint, self._registry)
        cause = self._record(
            (
                JournalEventKind.PLAN_VALIDATED
                if validated.state.value == "VALIDATED"
                else JournalEventKind.PLAN_REJECTED
            ),
            validated.plan_id,
            validated.plan_id,
            {
                "state": validated.state.value,
                "remainder_ids": tuple(
                    item.remainder_id for item in validated.remainders
                ),
            },
            causation_id=cause,
        )
        return self._continue(
            validated,
            blueprint,
            journal_position=journal_position,
            causation_id=cause,
            budget=budget,
            checkpoint=None,
            firewall_attestation=firewall_attestation,
        )

    def resume(
        self,
        checkpoint: RuntimeCheckpoint,
        blueprint: BlueprintSpec,
        *,
        budget: ExecutionBudget,
    ) -> ControllerResult:
        """Resume a paused plan with a fresh finite operational episode."""
        if checkpoint.plan.blueprint_id != blueprint.blueprint_id:
            raise ValueError("Checkpoint and blueprint IDs do not match")
        if checkpoint.plan.blueprint_version != blueprint.version:
            raise ValueError("Checkpoint and blueprint versions do not match")
        journal_position = self._journal.position if self._journal is not None else 0
        firewall_attestation = self._firewall.open_analysis(checkpoint.plan.objective)
        if not firewall_attestation.allows_execution:
            self._record_firewall(
                firewall_attestation.analysis_id,
                firewall_attestation,
            )
            self._escalate_firewall(firewall_attestation, checkpoint.plan.objective)
            raise FirewallInterventionError(firewall_attestation)
        cause = self._record_firewall(
            checkpoint.plan.plan_id,
            firewall_attestation,
        )
        cause = self._record(
            JournalEventKind.EXECUTION_RESUMED,
            checkpoint.plan.plan_id,
            checkpoint.checkpoint_id,
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "previous_segment_hash": checkpoint.journal_segment_hash,
                "new_max_operations": budget.max_operations,
            },
            causation_id=cause,
        )
        validated = self._validator.validate(
            checkpoint.plan, blueprint, self._registry
        )
        cause = self._record(
            (
                JournalEventKind.PLAN_VALIDATED
                if validated.state.value == "VALIDATED"
                else JournalEventKind.PLAN_REJECTED
            ),
            validated.plan_id,
            validated.plan_id,
            {
                "state": validated.state.value,
                "remainder_ids": tuple(
                    item.remainder_id for item in validated.remainders
                ),
            },
            causation_id=cause,
        )
        return self._continue(
            validated,
            blueprint,
            journal_position=journal_position,
            causation_id=cause,
            budget=budget,
            checkpoint=checkpoint,
            firewall_attestation=firewall_attestation,
        )

    def _continue(
        self,
        validated,
        blueprint: BlueprintSpec,
        *,
        journal_position: int,
        causation_id: str | None,
        budget: ExecutionBudget | None,
        checkpoint: RuntimeCheckpoint | None,
        firewall_attestation: FirewallAttestation,
    ) -> ControllerResult:
        authorization = self._effect_broker.authorize(
            validated, blueprint, self._registry
        )
        cause = self._record(
            (
                JournalEventKind.AUTHORIZATION_GRANTED
                if authorization.state.value == "AUTHORIZED"
                else JournalEventKind.AUTHORIZATION_DENIED
            ),
            validated.plan_id,
            authorization.authorization_id,
            {
                "state": authorization.state.value,
                "grant_ids": tuple(
                    grant.grant_id for grant in authorization.grants.values()
                ),
                "remainder_ids": tuple(
                    item.remainder_id for item in authorization.remainders
                ),
            },
            causation_id=causation_id,
        )
        execution = self._runtime.execute(
            validated,
            self._registry,
            authorization,
            self._effect_broker,
            self._journal,
            cause,
            budget,
            checkpoint,
        )
        cause = self._journal.last_event_id if self._journal is not None else cause
        ontology = self._ontology_evaluator.evaluate(execution)
        cause = self._record(
            JournalEventKind.ONTOLOGY_EVALUATED,
            validated.plan_id,
            validated.plan_id,
            {
                "report_count": len(ontology.reports),
                "structural_closed": ontology.execution.closure.structural_closed,
                "constitutional_closed": (
                    ontology.execution.closure.constitutional_closed
                ),
            },
            causation_id=cause,
        )
        epistemic = self._epistemic_evaluator.evaluate(ontology.execution)
        cause = self._record(
            JournalEventKind.EPISTEMIC_EVALUATED,
            validated.plan_id,
            validated.plan_id,
            {
                "report_count": len(epistemic.reports),
                "epistemic_closed": epistemic.execution.closure.epistemic_closed,
            },
            causation_id=cause,
        )
        final_kind = {
            "COMPLETED": JournalEventKind.OBJECTIVE_COMPLETED,
            "FAILED": JournalEventKind.EXECUTION_FAILED,
        }.get(epistemic.execution.state.value, JournalEventKind.OBJECTIVE_OPEN)
        self._record(
            final_kind,
            validated.plan_id,
            validated.plan_id,
            {
                "execution_state": epistemic.execution.state.value,
                "stopping_reason": epistemic.execution.closure.stopping_reason,
                "active_remainder_ids": tuple(
                    item.remainder_id
                    for item in epistemic.execution.closure.active_remainders
                ),
            },
            causation_id=cause,
        )
        journal_events = (
            self._journal.events_since(journal_position)
            if self._journal is not None else ()
        )
        archived_segment = None
        stored_checkpoint = None
        if self._journal_archive is not None:
            try:
                archived_segment = self._journal_archive.archive(journal_events)
            except JournalArchiveError as exc:
                remainder = self._archive_remainder(validated.plan_id, exc)
                epistemic = replace(
                    epistemic,
                    execution=replace(
                        epistemic.execution,
                        remainders=epistemic.execution.remainders + (remainder,),
                        closure=replace(
                            epistemic.execution.closure,
                            operational_converged=False,
                            stopping_reason="JOURNAL_ARCHIVE_FAILED",
                            active_remainders=(
                                epistemic.execution.closure.active_remainders
                                + (remainder,)
                            ),
                        ),
                    ),
                )
                self._record(
                    JournalEventKind.JOURNAL_ARCHIVE_FAILED,
                    validated.plan_id,
                    validated.plan_id,
                    {
                        "error_type": type(exc).__name__,
                        "remainder_id": remainder.remainder_id,
                    },
                    causation_id=(
                        journal_events[-1].event_id if journal_events else None
                    ),
                )
                journal_events = self._journal.events_since(journal_position)
        if (
            archived_segment is not None
            and epistemic.execution.checkpoint is not None
        ):
            linked_checkpoint = replace(
                epistemic.execution.checkpoint,
                journal_segment_hash=archived_segment.content_hash,
            )
            epistemic = replace(
                epistemic,
                execution=replace(
                    epistemic.execution,
                    checkpoint=linked_checkpoint,
                ),
            )
        if (
            self._checkpoint_store is not None
            and epistemic.execution.checkpoint is not None
            and archived_segment is not None
        ):
            try:
                stored_checkpoint = self._checkpoint_store.save(
                    epistemic.execution.checkpoint
                )
            except CheckpointStoreError as exc:
                remainder = self._checkpoint_remainder(validated.plan_id, exc)
                epistemic = replace(
                    epistemic,
                    execution=replace(
                        epistemic.execution,
                        remainders=epistemic.execution.remainders + (remainder,),
                        closure=replace(
                            epistemic.execution.closure,
                            operational_converged=False,
                            stopping_reason="CHECKPOINT_PERSISTENCE_FAILED",
                            active_remainders=(
                                epistemic.execution.closure.active_remainders
                                + (remainder,)
                            ),
                        ),
                    ),
                )
                self._record(
                    JournalEventKind.CHECKPOINT_PERSISTENCE_FAILED,
                    validated.plan_id,
                    epistemic.execution.checkpoint.checkpoint_id,
                    {
                        "error_type": type(exc).__name__,
                        "remainder_id": remainder.remainder_id,
                    },
                    causation_id=(
                        journal_events[-1].event_id if journal_events else None
                    ),
                )
                journal_events = self._journal.events_since(journal_position)
        return ControllerResult(
            plan=validated,
            authorization=authorization,
            execution=epistemic.execution,
            firewall_attestation=firewall_attestation,
            ontological_reports=ontology.reports,
            epistemic_reports=epistemic.reports,
            journal_events=journal_events,
            archived_journal_segment=archived_segment,
            stored_checkpoint=stored_checkpoint,
        )

    def _record_firewall(
        self,
        plan_id: str,
        attestation: FirewallAttestation,
    ) -> str | None:
        return self._record(
            (
                JournalEventKind.FIREWALL_DEVELOPMENT_BYPASS
                if attestation.mode is FirewallMode.DEVELOPMENT_BYPASS
                else (
                    JournalEventKind.FIREWALL_INTERVENED
                    if attestation.decision
                    in {FirewallDecision.QUARANTINE, FirewallDecision.DENY}
                    else JournalEventKind.FIREWALL_ATTESTED
                )
            ),
            plan_id,
            attestation.analysis_id,
            {
                "firewall_id": attestation.firewall_id,
                "policy_version": attestation.policy_version,
                "mode": attestation.mode.value,
                "present": attestation.present,
                "integrity_verified": attestation.integrity_verified,
                "constitutionally_valid": attestation.constitutionally_valid,
                "activated": attestation.activated,
                "decision": attestation.decision.value,
                "reason_codes": attestation.reason_codes,
                "input_digest": attestation.input_digest,
                "integrity_digest": attestation.integrity_digest,
            },
        )

    def _escalate_firewall(
        self,
        attestation: FirewallAttestation,
        objective: str,
    ) -> None:
        if self._firewall_escalation_handler is None:
            return
        self._firewall_escalation_handler(attestation, objective)

    def _record(
        self,
        kind: JournalEventKind,
        correlation_id: str,
        subject_ref: str,
        payload,
        *,
        causation_id: str | None = None,
    ) -> str | None:
        if self._journal is None:
            return None
        return self._journal.append(
            kind,
            correlation_id=correlation_id,
            subject_ref=subject_ref,
            payload=payload,
            causation_id=causation_id,
        ).event_id

    @staticmethod
    def _archive_remainder(plan_id: str, exc: JournalArchiveError):
        from fresta_diamond.contracts import Remainder, RemainderKind

        return Remainder(
            kind=RemainderKind.EXTERNAL_UNCERTAINTY,
            description=(
                "Journal archive failed after execution: "
                f"{type(exc).__name__}"
            ),
            required_for=plan_id,
            resolvable=True,
        )

    @staticmethod
    def _checkpoint_remainder(plan_id: str, exc: CheckpointStoreError):
        from fresta_diamond.contracts import Remainder, RemainderKind

        return Remainder(
            kind=RemainderKind.EXTERNAL_UNCERTAINTY,
            description=(
                "Checkpoint persistence failed after pause: "
                f"{type(exc).__name__}"
            ),
            required_for=plan_id,
            resolvable=True,
        )

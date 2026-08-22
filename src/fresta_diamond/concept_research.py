"""Bounded external concept research that produces unvalidated source units."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import html
import json
import re
import ssl
from typing import Any, Mapping
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from fresta_diamond.cognitive_workspace import (
    JsonlCognitiveWorkspace,
    SheetElement,
    SheetElementKind,
    SheetRevision,
    SheetState,
)
from fresta_diamond.concepts import ConceptRecord
from fresta_diamond.concept_validation import (
    ConceptAxisState,
    ConceptValidationReport,
)
from fresta_diamond.contracts import (
    Artifact,
    BlueprintSpec,
    CapabilityRequirement,
    ModuleManifest,
    OperationContract,
)
from fresta_diamond.effects import ExecutionContext
from fresta_diamond.registry import ModuleRegistry


CONCEPT_RESEARCH_REQUEST_SCHEMA = "artifact://concept-research-request@1"
CONCEPT_SOURCE_UNITS_SCHEMA = "artifact://concept-source-units@1"
CONCEPT_RESEARCH_CAPABILITY = "concept.research-external@1"
CONCEPT_SEARCH_EFFECT = "internet.search"
CONCEPT_SEARCH_PERMISSION = "internet.search:concept"
MAX_QUERY_CHARS = 1_000
MAX_TITLE_CHARS = 300
MAX_SOURCE_CONTENT_CHARS = 4_000


class ConceptResearchGapKind(str, Enum):
    MISSING_VOCABULARY = "MISSING_VOCABULARY"
    UNCERTAIN_BOUNDARY = "UNCERTAIN_BOUNDARY"
    COMPETING_DEFINITIONS = "COMPETING_DEFINITIONS"
    MISSING_RELATION = "MISSING_RELATION"
    EXTERNAL_RECOGNITION = "EXTERNAL_RECOGNITION"


@dataclass(frozen=True)
class ConceptResearchGap:
    kind: str
    target_ref: str
    description: str

    def __post_init__(self) -> None:
        if self.kind not in {
            ConceptResearchGapKind.MISSING_VOCABULARY,
            ConceptResearchGapKind.UNCERTAIN_BOUNDARY,
            ConceptResearchGapKind.COMPETING_DEFINITIONS,
            ConceptResearchGapKind.MISSING_RELATION,
            ConceptResearchGapKind.EXTERNAL_RECOGNITION,
        }:
            raise ValueError("Unknown concept research gap kind")
        if not self.target_ref.strip() or not self.description.strip():
            raise ValueError("Concept research gap references are required")


@dataclass(frozen=True)
class ConceptResearchQuery:
    query_id: str
    text: str
    purpose: str
    preferred_source_types: tuple[str, ...]
    reveals_candidate_label: bool = False

    def __post_init__(self) -> None:
        if not all((
            self.query_id.strip(),
            self.text.strip(),
            self.purpose.strip(),
        )):
            raise ValueError("Concept research query fields are required")
        if not self.preferred_source_types:
            raise ValueError("Concept query requires source preferences")


@dataclass(frozen=True)
class ConceptResearchRequest:
    request_id: str
    concept_ref: str
    scope: str
    gaps: tuple[ConceptResearchGap, ...]
    queries: tuple[ConceptResearchQuery, ...]
    max_results_per_query: int
    authority: str = "UNVALIDATED_RESEARCH_REQUEST"
    promotion_authority: bool = False

    def __post_init__(self) -> None:
        if not all((
            self.request_id.strip(),
            self.concept_ref.strip(),
            self.scope.strip(),
        )):
            raise ValueError("Concept research request references are required")
        if self.authority != "UNVALIDATED_RESEARCH_REQUEST":
            raise PermissionError("Research request cannot grant itself authority")
        if self.promotion_authority is not False:
            raise PermissionError("Research request cannot promote memory")
        if not self.gaps or not self.queries:
            raise ValueError("Concept research requires named gaps and queries")
        if not 1 <= len(self.queries) <= 6:
            raise ValueError("Concept research query budget must be between 1 and 6")
        if not 1 <= self.max_results_per_query <= 10:
            raise ValueError("Concept result budget must be between 1 and 10")
        ids = [item.query_id for item in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("Concept research contains duplicate query IDs")


@dataclass(frozen=True)
class ConceptSourceUnit:
    source_unit_id: str
    query_id: str
    title: str
    content: str
    source_locator: str
    source_type: str
    retrieved_at: str
    content_hash: str
    authority: str = "UNVALIDATED_EXTERNAL_SOURCE"

    def __post_init__(self) -> None:
        if not all((
            self.source_unit_id.strip(),
            self.query_id.strip(),
            self.title.strip(),
            self.content.strip(),
            self.source_locator.strip(),
            self.source_type.strip(),
            self.retrieved_at.strip(),
            self.content_hash.strip(),
        )):
            raise ValueError("External source unit fields are required")
        parsed = urlparse(self.source_locator)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("External source locator must be HTTP(S)")
        if self.authority != "UNVALIDATED_EXTERNAL_SOURCE":
            raise PermissionError("External source cannot validate itself")
        expected = sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_hash != expected:
            raise ValueError("External source content hash mismatch")


def build_concept_research_request(
    concept: ConceptRecord,
    report: ConceptValidationReport,
    *,
    max_queries: int = 4,
    max_results_per_query: int = 3,
    request_id: str | None = None,
    target_refs: tuple[str, ...] | None = None,
) -> ConceptResearchRequest:
    """Derive neutral-first queries from explicit gaps and concept structure."""

    report_applies = (
        report.concept_ref == concept.version_ref
        or (
            concept.previous_version_ref == report.concept_ref
            and report.validation_id in concept.validation_refs
        )
    )
    if not report_applies:
        raise ValueError("Research report belongs to another concept version")
    if not 1 <= max_queries <= 6:
        raise ValueError("max_queries must be between 1 and 6")
    gaps = _research_gaps(report)
    if target_refs is not None:
        selected_targets = tuple(dict.fromkeys(target_refs))
        if not selected_targets:
            raise ValueError("Targeted concept research requires target refs")
        gaps = tuple(
            gap for gap in gaps if gap.target_ref in set(selected_targets)
        )
    if not gaps:
        raise ValueError("Concept validation exposes no searchable gap")

    signature = concept.signature
    features = _join_terms(
        signature.characteristics,
        signature.functions,
        signature.constraints,
    )
    relations = _join_terms(signature.relations)
    exclusions = _join_terms(
        signature.exclusions,
        signature.counterexamples,
    )
    target_fields = {
        target.split(":", 2)[1]
        for target in (target_refs or ())
        if target.startswith("signature:") and target.count(":") >= 2
    }
    targeted = target_refs is not None
    proposed: list[ConceptResearchQuery] = []
    if features and (
        not targeted
        or bool(target_fields & {"characteristics", "functions", "constraints"})
    ):
        proposed.append(ConceptResearchQuery(
            query_id="query:features",
            text=f"{features} definição classificação conceito",
            purpose="Discover vocabulary without revealing the candidate label.",
            preferred_source_types=("ENCYCLOPEDIC", "ACADEMIC"),
        ))
    if relations and (not targeted or "relations" in target_fields):
        proposed.append(ConceptResearchQuery(
            query_id="query:relations",
            text=f"{relations} relação constitutiva conceito",
            purpose="Find recognized relations and candidate parent categories.",
            preferred_source_types=("ACADEMIC", "ENCYCLOPEDIC"),
        ))
    if (exclusions or features) and (
        not targeted
        or bool(target_fields & {"exclusions", "counterexamples", "examples"})
        or any(
            gap.kind == ConceptResearchGapKind.UNCERTAIN_BOUNDARY
            for gap in gaps
        )
    ):
        proposed.append(ConceptResearchQuery(
            query_id="query:boundaries",
            text=(
                f"{features} {exclusions} limites contraexemplos "
                "definições alternativas"
            ).strip(),
            purpose="Seek boundaries, competing definitions, and counterexamples.",
            preferred_source_types=("ACADEMIC", "ENCYCLOPEDIC"),
        ))
    if not targeted:
        labels = " ".join((concept.canonical_name, *concept.aliases))
        proposed.append(ConceptResearchQuery(
            query_id="query:label",
            text=f"{labels} definição conceito alternativas",
            purpose="Check recognition of the proposed label only after neutral queries.",
            preferred_source_types=("ENCYCLOPEDIC", "ACADEMIC"),
            reveals_candidate_label=True,
        ))
    queries = tuple(proposed[:max_queries])
    if queries and queries[0].reveals_candidate_label and len(proposed) > 1:
        raise ValueError("Candidate label cannot lead a nontrivial query plan")
    return ConceptResearchRequest(
        request_id=request_id or f"concept-research:{uuid4()}",
        concept_ref=concept.version_ref,
        scope=concept.scope,
        gaps=gaps,
        queries=queries,
        max_results_per_query=max_results_per_query,
    )


def concept_research_blueprint() -> BlueprintSpec:
    return BlueprintSpec(
        blueprint_id="workspace.research-concept",
        version=1,
        intent=(
            "Resolve named concept gaps with bounded external source discovery. "
            "Results remain unvalidated source units and must re-enter /learn."
        ),
        requirement=CapabilityRequirement(
            capability=CONCEPT_RESEARCH_CAPABILITY,
            input_name="research_request",
            input_schema=CONCEPT_RESEARCH_REQUEST_SCHEMA,
            output_name="source_units",
            output_schema=CONCEPT_SOURCE_UNITS_SCHEMA,
            contextual_roles=(1, 2, 3),
        ),
        allowed_effects=(CONCEPT_SEARCH_EFFECT,),
        granted_permissions=(CONCEPT_SEARCH_PERMISSION,),
    )


def concept_research_manifest() -> ModuleManifest:
    operation = OperationContract(
        operation_id="workspace.execute-concept-research",
        version="1.0.0",
        capabilities=(CONCEPT_RESEARCH_CAPABILITY,),
        inputs={"research_request": CONCEPT_RESEARCH_REQUEST_SCHEMA},
        outputs={"source_units": CONCEPT_SOURCE_UNITS_SCHEMA},
        effects=(CONCEPT_SEARCH_EFFECT,),
        permissions=(CONCEPT_SEARCH_PERMISSION,),
        determinism="EXTERNAL_READ",
    )
    return ModuleManifest(
        module_id="builtin.concept-research",
        version="1.0.0",
        kernel_contract=">=3.0,<4.0",
        sdk_contract=">=1.0,<2.0",
        operations=(operation,),
    )


def register_concept_research_provider(registry: ModuleRegistry) -> None:
    manifest = concept_research_manifest()
    registry.discover(manifest)
    report = registry.verify(manifest.module_id)
    if not report.admitted:
        raise RuntimeError("Built-in concept research provider was rejected")
    registry.enable(
        manifest.module_id,
        {manifest.operations[0].operation_id: _execute_concept_research},
    )


def research_request_artifact(request: ConceptResearchRequest) -> Artifact:
    return Artifact(
        schema=CONCEPT_RESEARCH_REQUEST_SCHEMA,
        payload={
            "request_id": request.request_id,
            "concept_ref": request.concept_ref,
            "scope": request.scope,
            "gaps": [
                {
                    "kind": item.kind,
                    "target_ref": item.target_ref,
                    "description": item.description,
                }
                for item in request.gaps
            ],
            "queries": [
                {
                    "query_id": item.query_id,
                    "text": item.text,
                    "purpose": item.purpose,
                    "preferred_source_types": list(
                        item.preferred_source_types
                    ),
                    "reveals_candidate_label": item.reveals_candidate_label,
                }
                for item in request.queries
            ],
            "max_results_per_query": request.max_results_per_query,
            "authority": request.authority,
            "promotion_authority": False,
        },
        provenance=(request.concept_ref,),
    )


def decode_source_units(artifact: Artifact) -> tuple[ConceptSourceUnit, ...]:
    if artifact.schema != CONCEPT_SOURCE_UNITS_SCHEMA:
        raise ValueError("Artifact is not a concept source-unit bundle")
    raw = artifact.payload.get("source_units")
    if not isinstance(raw, (list, tuple)):
        raise TypeError("source_units must be an array")
    return tuple(
        ConceptSourceUnit(
            source_unit_id=_text(item, "source_unit_id"),
            query_id=_text(item, "query_id"),
            title=_text(item, "title"),
            content=_text(item, "content"),
            source_locator=_text(item, "source_locator"),
            source_type=_text(item, "source_type"),
            retrieved_at=_text(item, "retrieved_at"),
            content_hash=_text(item, "content_hash"),
            authority=_text(item, "authority"),
        )
        for item in raw
        if isinstance(item, Mapping)
    )


def stage_source_units(
    workspace: JsonlCognitiveWorkspace,
    artifact: Artifact,
    *,
    sheet_id: str,
    concept_ref: str,
    title: str = "External concept research",
) -> SheetRevision:
    """Stage source reports as notes; existence in the sheet grants no truth."""

    units = decode_source_units(artifact)
    if not units:
        raise ValueError("Cannot stage an empty concept research result")
    if artifact.payload.get("concept_ref") != concept_ref:
        raise ValueError("Source-unit bundle belongs to another concept")
    revision = SheetRevision(
        sheet_id=sheet_id,
        revision_number=1,
        title=title,
        state=SheetState.STAGED,
        elements=tuple(
            SheetElement(
                element_id=f"source-unit:{item.source_unit_id}",
                kind=SheetElementKind.NOTE,
                content=f"{item.title}\n\n{item.content}",
                scope=_text(artifact.payload, "scope"),
                provenance=(item.source_locator,),
            )
            for item in units
        ),
        objective_ref=concept_ref,
        author_ref="actor:concept-research",
    )
    workspace.save(revision)
    return revision


@dataclass(frozen=True)
class WikipediaConceptSearchAdapter:
    """Optional concrete adapter; network access remains broker-controlled."""

    language: str = "pt"
    timeout_seconds: float = 20.0
    user_agent: str = "Fresta-Diamond/0.1 concept-research"

    def __call__(
        self,
        grant: Any,
        *,
        queries: tuple[Mapping[str, Any], ...],
        max_results_per_query: int,
    ) -> Mapping[str, Any]:
        if CONCEPT_SEARCH_PERMISSION not in grant.permissions:
            raise PermissionError("Concept search permission was not granted")
        results: list[dict[str, str]] = []
        endpoint = f"https://{self.language}.wikipedia.org/w/api.php"
        tls_context = _verified_system_ssl_context()
        for query in queries:
            query_id = _text(query, "query_id")
            text = _text(query, "text")
            params = urlencode({
                "action": "query",
                "list": "search",
                "srsearch": text,
                "srlimit": max_results_per_query,
                "format": "json",
                "utf8": 1,
            })
            request = Request(
                f"{endpoint}?{params}",
                headers={"User-Agent": self.user_agent},
            )
            with urlopen(
                request,
                timeout=self.timeout_seconds,
                context=tls_context,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            entries = (
                payload.get("query", {}).get("search", [])
                if isinstance(payload, Mapping) else []
            )
            for entry in entries[:max_results_per_query]:
                if not isinstance(entry, Mapping):
                    continue
                page_id = entry.get("pageid")
                title = entry.get("title")
                snippet = entry.get("snippet")
                if (
                    not isinstance(page_id, int)
                    or not isinstance(title, str)
                    or not isinstance(snippet, str)
                ):
                    continue
                results.append({
                    "query_id": query_id,
                    "title": title,
                    "snippet": _strip_html(snippet),
                    "url": (
                        f"https://{self.language}.wikipedia.org/?curid={page_id}"
                    ),
                    "source_type": "WIKIPEDIA",
                })
        return {"results": results}


def _execute_concept_research(
    inputs: Mapping[str, Mapping[str, Any]],
    context: ExecutionContext,
) -> Mapping[str, Mapping[str, Any]]:
    request = inputs.get("research_request")
    if not isinstance(request, Mapping):
        raise ValueError("Concept research request is required")
    if request.get("authority") != "UNVALIDATED_RESEARCH_REQUEST":
        raise PermissionError("Research input attempted to grant authority")
    if request.get("promotion_authority") is not False:
        raise PermissionError("Research input attempted to promote memory")
    request_id = _text(request, "request_id")
    concept_ref = _text(request, "concept_ref")
    scope = _text(request, "scope")
    raw_queries = request.get("queries")
    if not isinstance(raw_queries, (list, tuple)) or not raw_queries:
        raise ValueError("Research request contains no queries")
    if len(raw_queries) > 6:
        raise ValueError("Research query budget exceeded")
    raw_gaps = request.get("gaps")
    if not isinstance(raw_gaps, (list, tuple)) or not raw_gaps:
        raise ValueError("Research request contains no named gaps")
    for gap in raw_gaps:
        if not isinstance(gap, Mapping):
            raise TypeError("Research gap must be an object")
        ConceptResearchGap(
            kind=_text(gap, "kind"),
            target_ref=_text(gap, "target_ref"),
            description=_text(gap, "description"),
        )
    query_ids = {
        _text(item, "query_id")
        for item in raw_queries
        if isinstance(item, Mapping)
    }
    if len(query_ids) != len(raw_queries):
        raise ValueError("Research queries are malformed or duplicated")
    reveal_positions: list[int] = []
    for index, query in enumerate(raw_queries):
        if not isinstance(query, Mapping):
            raise TypeError("Research query must be an object")
        text = _text(query, "text")
        if len(text) > MAX_QUERY_CHARS:
            raise ValueError("Research query exceeds the text budget")
        preferences = query.get("preferred_source_types")
        if not isinstance(preferences, (list, tuple)) or not preferences:
            raise ValueError("Research query lacks source preferences")
        reveal = query.get("reveals_candidate_label")
        if not isinstance(reveal, bool):
            raise TypeError("Query label-disclosure marker must be boolean")
        if reveal:
            reveal_positions.append(index)
    if reveal_positions and reveal_positions != [len(raw_queries) - 1]:
        raise ValueError("A label-revealing query must be unique and last")
    maximum = request.get("max_results_per_query")
    if (
        not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or not 1 <= maximum <= 10
    ):
        raise ValueError("Research result budget is invalid")
    response = context.invoke(
        CONCEPT_SEARCH_EFFECT,
        queries=tuple(raw_queries),
        max_results_per_query=maximum,
    )
    if not isinstance(response, Mapping):
        raise ValueError("Concept search adapter returned no result bundle")
    raw_results = response.get("results")
    if not isinstance(raw_results, (list, tuple)):
        raise ValueError("Concept search adapter results must be an array")

    per_query: dict[str, int] = {query_id: 0 for query_id in query_ids}
    units: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for item in raw_results:
        if not isinstance(item, Mapping):
            raise TypeError("Concept search result must be an object")
        query_id = _text(item, "query_id")
        if query_id not in query_ids:
            raise ValueError("Search result references an unknown query")
        if per_query[query_id] >= maximum:
            continue
        title = _text(item, "title")
        content = _text(item, "snippet")
        if len(title) > MAX_TITLE_CHARS:
            title = title[:MAX_TITLE_CHARS].rstrip()
        if len(content) > MAX_SOURCE_CONTENT_CHARS:
            content = content[:MAX_SOURCE_CONTENT_CHARS].rstrip()
        locator = _text(item, "url")
        source_type = _text(item, "source_type")
        parsed = urlparse(locator)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Search result locator must be HTTP(S)")
        duplicate_key = (locator, content)
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        per_query[query_id] += 1
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        source_unit_id = sha256(
            f"{query_id}\0{locator}\0{content_hash}".encode("utf-8")
        ).hexdigest()[:32]
        units.append({
            "source_unit_id": source_unit_id,
            "query_id": query_id,
            "title": title,
            "content": content,
            "source_locator": locator,
            "source_type": source_type,
            "retrieved_at": retrieved_at,
            "content_hash": content_hash,
            "authority": "UNVALIDATED_EXTERNAL_SOURCE",
        })
    return {
        "source_units": {
            "request_id": request_id,
            "concept_ref": concept_ref,
            "scope": scope,
            "source_units": units,
            "authority": "UNVALIDATED_EXTERNAL_SOURCE_BUNDLE",
            "promotion_authority": False,
            "required_next_step": "workspace.stage_then_learn",
        }
    }


def _research_gaps(
    report: ConceptValidationReport,
) -> tuple[ConceptResearchGap, ...]:
    gaps: list[ConceptResearchGap] = []
    if report.recognition_state is ConceptAxisState.NOT_EVALUATED:
        gaps.append(ConceptResearchGap(
            ConceptResearchGapKind.EXTERNAL_RECOGNITION,
            report.concept_ref,
            "Check whether an equivalent concept is externally recognized.",
        ))
    if report.definition_state is ConceptAxisState.INDETERMINATE:
        gaps.append(ConceptResearchGap(
            ConceptResearchGapKind.COMPETING_DEFINITIONS,
            report.concept_ref,
            "Compare definitions, boundaries, and counterexamples.",
        ))
    for remainder in report.active_remainders:
        description = remainder.description.casefold()
        if "relation" in description:
            kind = ConceptResearchGapKind.MISSING_RELATION
        elif "target" in description or "concept part" in description:
            kind = ConceptResearchGapKind.UNCERTAIN_BOUNDARY
        elif remainder.kind.value == "EXTERNAL_UNCERTAINTY":
            kind = ConceptResearchGapKind.MISSING_VOCABULARY
        else:
            continue
        gap = ConceptResearchGap(
            kind,
            remainder.required_for,
            remainder.description,
        )
        if gap not in gaps:
            gaps.append(gap)
    return tuple(gaps)


def _join_terms(*groups: tuple[str, ...]) -> str:
    values = tuple(
        value
        for group in groups
        for value in group
        if value.strip()
    )
    return "; ".join(values)


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be non-empty text")
    return " ".join(item.split())


def _strip_html(value: str) -> str:
    return " ".join(
        html.unescape(re.sub(r"<[^>]+>", " ", value)).split()
    )


def _verified_system_ssl_context() -> ssl.SSLContext:
    """Use normal verification, supplementing OpenSSL with Windows roots."""

    enum_certificates = getattr(ssl, "enum_certificates", None)
    if enum_certificates is None:
        return ssl.create_default_context()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    loaded = 0
    for certificate, encoding, _trust in enum_certificates("ROOT"):
        if encoding != "x509_asn":
            continue
        try:
            context.load_verify_locations(
                cadata=ssl.DER_cert_to_PEM_cert(certificate)
            )
            loaded += 1
        except ssl.SSLError:
            continue
    return context if loaded else ssl.create_default_context()

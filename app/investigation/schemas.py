"""Typed evidence and hypothesis contracts; observations never become LLM measurements."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceItem(BaseModel):
    """A source-backed observation, user claim, guidance excerpt or model inference."""

    model_config = ConfigDict(extra="forbid")
    id: str
    modality: str
    kind: Literal["user_claim", "model_inference", "document_guidance", "measurement"]
    source_id: str
    origin_id: str | None = None
    observation: str
    locator: str | None = None
    reliability: Literal["low", "medium", "high"] = "low"
    asset_identity: str | None = None
    predicate: str | None = None
    value: Any = None
    limitations: list[str] = Field(default_factory=list)


class Case(BaseModel):
    """Request context and actual normalized evidence."""

    question: str
    conversation_id: str
    evidence: list[EvidenceItem]
    linked_asset: bool = False
    parent_case_id: str | None = None
    asset_id: str | None = Field(default=None, max_length=100)
    asset_identity_source: (
        Literal["user_question", "source_declared_unverified"] | None
    ) = None
    as_of: str | None = Field(default=None, max_length=50)

    @field_validator("as_of")
    @classmethod
    def cutoff(cls, value: str | None) -> str | None:
        """Require an explicit knowledge clock for historical evidence investigations."""
        from app.simulation.repository import utc

        return utc(value) if value is not None else None


class ExpectedSign(BaseModel):
    """An explicit hypothesis prerequisite; only measured predicates can falsify it."""

    predicate: str
    expected_value: bool


class Hypothesis(BaseModel):
    """A proposed mechanism with auditable support, conflicts and missing checks."""

    model_config = ConfigDict(extra="forbid")
    id: str
    mechanism: str = Field(max_length=700)
    assumptions: list[str] = Field(max_length=8)
    expected_signs: list[ExpectedSign] = Field(max_length=8)
    supporting_evidence_ids: list[str] = Field(max_length=32)
    contradicting_evidence_ids: list[str] = Field(max_length=32)
    missing_tests: list[str] = Field(max_length=8)


class Proposal(BaseModel):
    """Bounded LLM proposals, not facts or calibrated probabilities."""

    model_config = ConfigDict(extra="forbid")
    hypotheses: list[Hypothesis] = Field(min_length=0, max_length=8)
    follow_up_queries: list[str] = Field(max_length=2)
    unresolved: list[str] = Field(max_length=5)


class ToolCall(BaseModel):
    """Actual tool execution provenance and elapsed time."""

    tool: str
    status: str
    provider: str | None = None
    model: str | None = None
    elapsed_seconds: float
    source_ids: list[str] = Field(default_factory=list)
    generation_attempts: int | None = None


class Investigation(BaseModel):
    """Persistable case result with transparent ranking and limitations."""

    case: Case
    hypotheses: list[dict]
    tools: list[ToolCall]
    rounds: int
    unresolved: list[str]
    limitations: list[str]
    stop_reason: str = "not_recorded_in_legacy_case"
    hypothesis_revisions: list[dict] = Field(default_factory=list)
    followup_error: dict[str, str] | None = None
    case_key: str | None = None
    hypothesis_registry: list[dict] = Field(default_factory=list)
    claim_verification: list[dict] = Field(default_factory=list)
    excluded_evidence: list[dict] = Field(default_factory=list)
    quality_issues: list[dict] = Field(default_factory=list)

"""Typed specialist outputs shared by the real orchestrator and additive API."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ToolOutput(BaseModel):
    """Preserve legacy fields while validating the source-identity boundary."""

    model_config = ConfigDict(extra="allow")
    evidence_ids: list[str] = Field(default_factory=list)


class VisionOutput(ToolOutput):
    """Actual model observations, explicitly distinct from physical measurements."""

    analysis: dict[str, Any]


class TranscriptOutput(ToolOutput):
    """Unverified automatic transcript; user speech is input provenance."""

    transcript: dict[str, Any]


class RetrievalOutput(ToolOutput):
    """Real source excerpts; relevance scores never imply evidential support."""

    passages: list[dict[str, Any]]


class PredictionOutput(ToolOutput):
    """Unchanged native predictor result and its resolvable source identities."""

    prediction: dict[str, Any]


class MeasurementOutput(ToolOutput):
    """Actual deterministic statistics with original measurement metadata."""


class DocumentSection(BaseModel):
    """An exact bounded excerpt of a stored source chunk."""

    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    attachment_id: str
    locator: str
    text: str
    excerpted: bool


class DocumentOutput(ToolOutput):
    """Extraction only; no generated rows, interpretation or invented pages."""

    sections: list[DocumentSection]
    attachment_id: str
    total_chunks: int
    selected_characters: int
    extraction: Literal[
        "stored_deterministic_extraction", "on_demand_deterministic_csv"
    ]


class GeneratedAudio(BaseModel):
    """Actual bounded local WAV and model provenance; not engineering evidence."""

    model_config = ConfigDict(extra="forbid")
    mime: Literal["audio/wav"] = "audio/wav"
    audio_base64: str
    sha256: str
    sample_rate: int = Field(gt=0)
    frames: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    provider: str
    model: str
    voice_id: int = Field(ge=0)
    speed: float = Field(gt=0)
    spoken_text: str
    warnings: list[str]
    cache: dict[str, Any]
    phase_timings: dict[str, float]
    resources: dict[str, Any] = Field(default_factory=dict)
    original_synthesis_resources: dict[str, Any] = Field(default_factory=dict)
    worker_lifecycle: dict[str, Any] = Field(default_factory=dict)
    worker_fallback: dict[str, Any] = Field(default_factory=dict)
    model_reused: bool = False
    model_hashes: dict[str, str] = Field(default_factory=dict)


class SpeechOutput(ToolOutput):
    """Audio output without fabricated evidence IDs or public file paths."""

    audio: GeneratedAudio


class VideoOutput(ToolOutput):
    """Sparse frame observations; missing intervals remain unobserved."""

    video: dict[str, Any]
    frames: list[dict[str, Any]]
    limitations: list[str]


SpecialistTool = Literal[
    "vision.inspect",
    "audio.transcript",
    "speech.synthesize",
    "document.extract",
    "measurements.profile",
    "video.frames",
    "video.inspect",
    "knowledge.retrieve",
    "prediction.run",
]


class SpecialistRequest(BaseModel):
    """Dispatch only whitelisted, independently typed tool arguments in one case."""

    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)
    tool_id: SpecialistTool
    arguments: dict[str, Any] = Field(default_factory=dict)


class SpecialistResponse(BaseModel):
    """Consistent result envelope backed by an actual persisted runner trace."""

    model_config = ConfigDict(extra="forbid")
    request_id: str
    run_id: str
    tool_id: SpecialistTool
    status: Literal["complete", "cancelled", "error"]
    elapsed_seconds: float
    evidence_ids: list[str] = Field(default_factory=list)
    output_role: Literal["observations", "input_provenance", "generated_audio"]
    output: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SpecialistCancel(BaseModel):
    """Cancellation remains scoped to the originating conversation and request."""

    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)

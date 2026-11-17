"""One discoverable inventory of real installed adapters, native models and explicit optional gaps."""

from typing import Literal
import httpx
from pydantic import BaseModel, Field
from app.core.config import ROOT, SETTINGS
from app.core.errors import SireError
from app.media import runtime
from app.prediction.hub import catalog
from app.providers.adapter import OllamaAdapter
from app.providers.ollama import HTTP_TLS_CONTEXT, _base
from app.providers.resources import SCHEDULER


class ProviderDescriptor(BaseModel):
    """Configuration/availability is separate from measured inference and physical acceptance."""

    id: str
    provider: str
    model: str
    version: str | None = None
    capabilities: list[str]
    location: str
    license: str
    dependencies: list[str]
    adapter: str | None
    input_schema: dict
    output_schema: dict
    availability: Literal["configured", "unavailable", "optional_not_installed"]
    health: str
    streaming: list[str] = Field(default_factory=list)
    context_limit: int | None = None
    weights_bytes: int | None = None
    measured_resources: dict | None = None
    benchmarks: list[dict] = Field(default_factory=list)
    fallback_provider: str | None = None


def _contract(name: str) -> dict:
    return {"$ref": f"/openapi.json#/components/schemas/{name}"}


def providers() -> list[ProviderDescriptor]:
    """Discover installed local specialists without importing neural runtimes or loading weights."""
    descriptors = []
    try:
        installed = OllamaAdapter().list_models()
        with httpx.Client(
            timeout=3, trust_env=False, verify=HTTP_TLS_CONTEXT
        ) as client:
            version = client.get(_base() + "/api/version").json().get("version")
    except (SireError, httpx.HTTPError, ValueError):
        installed, version = [], None
    actual = {row["name"]: row for row in installed}
    declared = {}
    with httpx.Client(timeout=3, trust_env=False, verify=HTTP_TLS_CONTEXT) as client:
        for name in actual:
            try:
                response = client.post(_base() + "/api/show", json={"model": name})
                response.raise_for_status()
                declared[name] = response.json()
            except (httpx.HTTPError, ValueError, SireError):
                declared[name] = {}

    for name in sorted(
        set(actual) | {SETTINGS["text_model"], SETTINGS["vision_model"]}
    ):
        row = actual.get(name)
        # Configured role, not a claim that an untested tag has passed capability acceptance.
        info = declared.get(name, {})
        capabilities = ["text"]
        if "vision" in info.get("capabilities", []) or name == SETTINGS["vision_model"]:
            capabilities.append("vision")
        capability = "vision" if "vision" in capabilities else "text"
        license_text = info.get("license", "")
        license_name = (
            "Apache-2.0 (local distribution declaration)"
            if "Apache License" in license_text and "Version 2.0" in license_text
            else "Model distribution license not verified"
        )

        descriptors.append(
            ProviderDescriptor(
                id="ollama:" + name,
                provider="ollama",
                model=name,
                version=version,
                capabilities=capabilities,
                location="local://ollama/" + name,
                license=license_name,
                dependencies=["existing Ollama loopback service"],
                adapter="app.providers.adapter.OllamaAdapter",
                input_schema=_contract("ChatRequest"),
                output_schema={
                    "type": "object",
                    "description": "Actual SSE events / typed vision evidence; see frontend handoff",
                },
                availability="configured" if row else "unavailable",
                health=(
                    "Installed tag discovered; configured-role inference is independently tested"
                    if row
                    else "Tag absent or local provider unavailable"
                ),
                streaming=["text"] if capability == "text" else [],
                context_limit=(
                    SETTINGS["vision_context_length"]
                    if capability == "vision"
                    else SETTINGS["context_length"]
                ),
                weights_bytes=row["size"] if row else None,
            )
        )
    ready = runtime.readiness()
    for kind, model, license_name, contract, adapter in [
        (
            "asr",
            "whisper-tiny.en-int8",
            "MIT",
            "Body_transcribe_api_v1_voice_transcribe_post",
            "app.voice.service.transcribe_bytes",
        ),
        (
            "tts",
            "kokoro-en-v0.19-int8",
            "Apache-2.0",
            "SpeechRequest",
            "app.media.runtime.run",
        ),
    ]:
        try:
            paths = runtime.model_files(kind, verify=False)
        except SireError:
            paths = {}
        descriptors.append(
            ProviderDescriptor(
                id="sherpa:" + kind,
                provider="sherpa-onnx",
                model=model,
                capabilities=[kind],
                location=(
                    (runtime.MODELS / runtime.POLICY["models"][kind]["directory"])
                    .relative_to(ROOT)
                    .as_posix()
                    if runtime.MODELS.is_relative_to(ROOT)
                    else "configured local model directory"
                ),
                license=license_name,
                dependencies=["isolated sherpa_onnx runtime"],
                adapter=adapter,
                input_schema=_contract(contract),
                output_schema=(
                    {"type": "string", "contentMediaType": "audio/wav"}
                    if kind == "tts"
                    else {
                        "type": "object",
                        "description": "Actual unverified English transcript and whole-recording window",
                    }
                ),
                availability=(
                    "configured" if ready[kind + "_configured"] else "unavailable"
                ),
                health=(
                    "Pinned files and previous worker probe present"
                    if ready[kind + "_ready"]
                    else "Worker not independently ready"
                ),
                weights_bytes=(
                    sum(p.stat().st_size for p in paths.values()) if paths else None
                ),
            )
        )
    descriptors.extend(
        [
            ProviderDescriptor(
                id="local:retrieval",
                provider="deterministic",
                model="lexical source-filtered retrieval",
                capabilities=["retrieval"],
                location="local://sqlite/chunks",
                license="Repository code and existing dependencies",
                dependencies=["SQLite"],
                adapter="app.knowledge.search.search",
                input_schema={
                    "type": "object",
                    "required": ["conversation_id", "query"],
                },
                output_schema={
                    "type": "array",
                    "description": "Exact excerpts with page/section locators",
                },
                availability="configured",
                health="Semantic embeddings are optional and not configured by default",
            ),
            ProviderDescriptor(
                id="local:video",
                provider="opencv",
                model="bounded representative frame decoder",
                capabilities=["video_frames"],
                location=".runtime/optional_deps",
                license="Existing OpenCV/media dependency provenance: docs/MEDIA_PROVENANCE.md",
                dependencies=["isolated cv2 runtime"],
                adapter="app.media.runtime.run",
                input_schema={
                    "type": "string",
                    "description": "Validated bounded private video file",
                },
                output_schema={
                    "type": "object",
                    "description": "Real frame bytes, decoder timestamps and hashes; no continuous-motion claim",
                },
                availability="configured" if ready["video_ready"] else "unavailable",
                health=(
                    "Configured decoder probe present"
                    if ready["video_ready"]
                    else "Decoder not ready"
                ),
            ),
        ]
    )
    for item in catalog():
        descriptors.append(
            ProviderDescriptor(
                id="native:" + item["model_id"],
                provider="preserved_native",
                model=item["model_id"],
                version=item.get("version"),
                capabilities=["native_" + item["task"]],
                location=item["artifact_dir"],
                license="Preserved research artifacts; dependency provenance retained",
                dependencies=[
                    "preserved dataset-specific preprocessor and native worker"
                ],
                adapter="app.prediction.hub.predict",
                input_schema=_contract("PredictionRequest"),
                output_schema={
                    "type": "object",
                    "description": "Original saved-model output with dataset-specific provenance",
                },
                availability=(
                    "configured"
                    if (ROOT / item["artifact_dir"]).is_dir()
                    else "unavailable"
                ),
                health="Historical route verification: " + str(item["status"]),
            )
        )
    for identifier, capability, model, license_name in [
        ("optional:qwen-asr", "asr", "Qwen3-ASR-0.6B", "Apache-2.0"),
        ("optional:qwen-tts", "tts", "Qwen3-TTS-0.6B", "Apache-2.0"),
        ("optional:silero", "vad", "Silero VAD", "MIT"),
    ]:
        if identifier == "optional:silero" and ready.get("vad_configured"):
            path = runtime.model_files("vad", verify=False)["silero_vad.onnx"]
            descriptors.append(
                ProviderDescriptor(
                    id="sherpa:vad",
                    provider="sherpa-onnx",
                    model="silero_vad.onnx",
                    capabilities=["vad"],
                    location=".runtime/media_models/silero-vad",
                    license="MIT",
                    dependencies=["existing isolated sherpa_onnx runtime"],
                    adapter="app.voice.vad.VadStream",
                    input_schema={
                        "type": "string",
                        "description": "Bounded PCM16 mono16kHz",
                    },
                    output_schema={
                        "type": "object",
                        "description": "Actual unverified speech boundaries in source sample clock",
                    },
                    availability="configured",
                    health=(
                        "Actual isolated worker initialized"
                        if ready.get("vad_ready")
                        else "Pinned files installed; worker probe pending"
                    ),
                    streaming=["speech_boundaries"],
                    weights_bytes=path.stat().st_size,
                )
            )
            continue
        descriptors.append(
            ProviderDescriptor(
                id=identifier,
                provider="optional",
                model=model,
                capabilities=[capability],
                location="not installed",
                license=license_name,
                dependencies=[
                    "Separate compatible runtime and pinned local weights required"
                ],
                adapter=None,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                availability="optional_not_installed",
                health="No adapter activation, compatibility acceptance or benchmark claimed",
            )
        )
    return descriptors


def resources() -> dict:
    """Combine actual scheduler state and Ollama residency; never infer GPU use from hardware presence."""
    try:
        response = httpx.get(
            _base() + "/api/ps", timeout=3, trust_env=False, verify=HTTP_TLS_CONTEXT
        )
        response.raise_for_status()
        loaded = response.json()
    except (httpx.HTTPError, ValueError, SireError):
        loaded = {"status": "unavailable", "models": None}
    return {
        "scheduler": SCHEDULER.snapshot(),
        "ollama_residency": loaded,
        "residency_policy": f"keep_alive={SETTINGS['ollama_keep_alive_seconds']}s; one heavy operation across cooperating local workers; launcher limits Ollama to one loaded model",
    }

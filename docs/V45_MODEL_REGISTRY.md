# V4.5 provider/model registry

`GET /api/v1/providers/registry` returns typed `ProviderDescriptor` records. The actual local discovery contains179descriptors:4installed Ollama tags,168preserved native routes, Whisper, Kokoro, Silero, lexical retrieval, video extraction and2optional Qwen speech gaps. Availability means configured/discovered, not a new successful inference. Actual current residency is separately queried through `/runtime/resources` and Ollama `/api/ps`.

Each descriptor carries capabilities, version when known, local location, declared license, dependencies, adapter, schema references, health/readiness, supported streaming shape and configured context limit where applicable. Unmeasured resource/benchmark fields remain null/empty. No guessed VRAM or context capabilities are advertised as measured. Ollama `/api/show` supplies actual tag capabilities and distribution-license declaration; that declaration is not an independent upstream license audit.

| Role | Installed path/provider | State |
|---|---|---|
| Text | `qwen3:4b-instruct`, local Ollama | Real ordinary and hypothesis inference tested |
| Vision | `qwen3-vl:2b-instruct`, local Ollama | Real image inference tested; observations remain unverified |
| Additional aliases | `qwen3:4b`, `qwen3-vl:2b` | Tags discovered; no claim of new independent acceptance for every alias |
| ASR | `.runtime/media_models/whisper-tiny-en`, isolated Sherpa2.0.1 | Pinned hashes, real English file/network transcript |
| TTS | `.runtime/media_models/kokoro-en`, isolated Sherpa2.0.1 | Pinned hashes, real24kHz WAV; physical playback unverified |
| VAD | `.runtime/media_models/silero-vad/silero_vad.onnx` |643854bytes; SHA256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`; MIT; real worker |
| Retrieval | Existing local lexical adapter | Actual document retrieval; no invented embedding benchmark |
| Prediction | `ml/registry/catalog.json` |168original routes retained; selected12roles validated on saved samples |
| Video | Existing local decoder worker |3bounded extracted frames verified |
| Qwen ASR/TTS | No installed adapters/packages | Explicitly deferred; not aliases to Whisper/Kokoro |

Qwen speech was not installed into the preserved environment. Official [ASR dependencies](https://github.com/QwenLM/Qwen3-ASR/blob/main/pyproject.toml) pin Transformers4.57.6, while [TTS dependencies](https://github.com/QwenLM/Qwen3-TTS/blob/main/pyproject.toml) pin4.57.3. Neither package/Transformers was present. A future isolated, pinned compatibility evaluation is required; simultaneous support is not inferred from similar names.

Silero weights came from the official [Sherpa model release](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx); its [upstream license](https://github.com/snakers4/silero-vad/blob/master/LICENSE) is MIT. The observed hash is pinned; no independent publisher signature is claimed. `scripts/setup_vad.py` reproduces the bounded official acquisition and refuses a mismatched cached file.

The only new Python transport dependency is MIT `wsproto==1.2.0`, installed in project `.venv/Lib/site-packages`; existing external environment and h11 remain unchanged. App/runtime requirement files carry the pin. Native CUDA/driver/GPU changes were not attempted.

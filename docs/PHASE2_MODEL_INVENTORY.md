# Phase 2 model inventory

Actual inventory snapshot: `.runtime/phase2_20261118/main_cutover.json`; current endpoint `/api/v1/providers/registry`. Installed discovery is not proof that every historical model route was freshly tested. Native historical/unavailable catalog entries remain preserved; the twelve selected primary routes were actually executed.

| Provider | Runtime | Quantization | Discovered availability |
|---|---|---|---|
| ollama:qwen3-vl:2b | ollama | Q4_K_M | configured |
| ollama:qwen3-vl:2b-instruct | ollama | Q4_K_M | configured |
| ollama:qwen3:4b | ollama | Q4_K_M | configured |
| ollama:qwen3:4b-instruct | ollama | Q4_K_M | configured |
| sherpa:asr | sherpa-onnx | int8 (configured weights) | configured |
| sherpa:tts | sherpa-onnx | int8 (configured weights) | configured |
| sherpa:asr-tiny | sherpa-onnx | int8 (configured weights) | configured |
| local:embeddings | ONNX Runtime CPU | uint8 | configured |
| local:documents | python | not measured | configured |
| local:retrieval | sqlite lexical | not measured | configured |
| local:video | OpenCV/FFmpeg | not measured | configured |
| optional:qwen-asr | not measured | not measured | optional_not_installed |
| optional:qwen-tts | not measured | not measured | optional_not_installed |
| sherpa:vad | not measured | not measured | configured |

Actual post-resume CLI reports `qwen3:4b-instruct`, **100% GPU**, 3.2GB, context4096, llamacpp. Detailed byte-level `/api/ps` and `nvidia-smi` are retained in `resume_runtime.json`. Phase 1 offload logs verified text37/37 and vision29/29 plus CLIP on GPU; Phase 2 active-vision cancellation also observed positive VLM VRAM. Current GPU utilization is a point-in-time observation, not inference-average utilization. No new Qwen tag or GPU runtime was installed in Phase 2.

Default ASR is Whisper **base.en int8**, selected after actual small-sample comparison; original tiny.en is the explicit `profile=asr` fallback. Failure does not silently switch models. Silero and Kokoro retain original files. Whisper confidence remains unavailable rather than invented.

Added only **11 pinned assets / 200,750,848 bytes** (model/runtime assets, excluding metadata/license HTTP requests). MiniLM-L6-v2 revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` runs uint8 ONNX on CPU with384-dimensional vectors, two threads,256token bound, batch16. Base ASR revision: `59eea950fc76df2453efb57e6c0fd334548e8ffe`.

Wheel paths below are the reviewed installer destinations. Initial provisioning used the private `candidate_downloads` cache for the same SHA-verified wheels, then installed only into `.runtime/semantic_deps`.

| Reviewed manifest target | Bytes | SHA256 |
|---|---:|---|
| `.runtime/semantic_models/minilm-l6-v2/config.json` | 612 | `953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41` |
| `.runtime/semantic_models/minilm-l6-v2/onnx/model_quint8_avx2.onnx` | 23,046,789 | `b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21` |
| `.runtime/semantic_models/minilm-l6-v2/tokenizer.json` | 466,247 | `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037` |
| `.runtime/semantic_models/minilm-l6-v2/tokenizer_config.json` | 350 | `acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b` |
| `.runtime/media_models/whisper-base.en/base.en-decoder.int8.onnx` | 130,669,978 | `f7162ad6db2dbef16cfaeaa7f945b9d7dd9c1b8d472f6aca82f2273d185e4d41` |
| `.runtime/media_models/whisper-base.en/base.en-encoder.int8.onnx` | 29,120,534 | `ef6b936f4c9b1d90a3b68634b60c4ed8576b26172b33c2535ec0e933c9edb823` |
| `.runtime/media_models/whisper-base.en/base.en-tokens.txt` | 835,554 | `306cd27f03c1a714eca7108e03d66b7dc042abe8c258b44c199a7ed9838dd930` |
| `.runtime/phase2_setup/wheels/onnxruntime-1.23.2-cp311-cp311-win_amd64.whl` | 13,468,349 | `902c756d8b633ce0dedd889b7c08459433fbcf35e9c38d1c03ddc020f0648c6e` |
| `.runtime/phase2_setup/wheels/tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2,674,684 | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| `.runtime/phase2_setup/wheels/flatbuffers-25.9.23-py2.py3-none-any.whl` | 30,869 | `255538574d6cb6d0a79a17ec8bc0d30985913b87513a01cce8bcdb6b4c44d0e2` |
| `.runtime/phase2_setup/wheels/protobuf-6.33.0-cp310-abi3-win_amd64.whl` | 436,882 | `9a031d10f703f03768f2743a1c403af050b6ae1f3480e9c140f39c45f81b13ee` |

License checks: [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) declares Apache-2.0; [Whisper](https://github.com/openai/whisper/blob/main/LICENSE) uses MIT; existing Sherpa is Apache-2.0. Reviewed isolated runtimes: [ONNX Runtime1.23.2](https://pypi.org/project/onnxruntime/1.23.2/) MIT, [Tokenizers0.22.1](https://pypi.org/project/tokenizers/0.22.1/) Apache-2.0, Flatbuffers Apache-2.0 and Protobuf BSD. Tokenizers wheel lacked a license file: installation initially stopped, then the exact [v0.22.1 upstream license](https://raw.githubusercontent.com/huggingface/tokenizers/v0.22.1/LICENSE) and package classifier were verified. Failure evidence retained. No GPL/AGPL/non-commercial dependency added.

Reproduction: `python scripts/setup_phase2_specialists.py` reviews the exact manifest without downloads. `--install --group all` performs explicit size/SHA-checked bounded installation; `--group semantic` or `asr_base` scopes it. It never replaces a conflicting existing candidate. Four pins are in `requirements-semantic.txt`; root `.venv` is unchanged. Reviewed wheels target Windows x64; other platforms require separately reviewed compatible wheels. Existing source packages/data/environment are required; a clean disconnected fresh host was not validated.

DEFERRED: Qwen3-VL4B (existing2B pathway works on this6GB GPU), Qwen ASR/TTS, Piper and dedicated video LLM. No measured justification to add them in this sprint. No suitable OCR engine installed. Working Kokoro retained; Phase 2 chunk delivery does not establish a faster synthesis engine or improved speech quality.

Per-worker observed CPU lifetime and peak RSS are exported in [validation summary](PHASE2_VALIDATION_SUMMARY.json). OS counters include initialization/imports, not system-wide peak RAM. Startup/per-asset CPU/GPU utilization not measured remains unknown; no guessed RAM/VRAM costs are reported.

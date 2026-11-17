# V3.2 optional local media provenance

The original Python environment and trained NASA models are unchanged. Optional packages live only in ignored `.runtime/optional_deps`; speech weights live in `.runtime/media_models`. Startup performs no downloads. `config/media.yaml` pins every loaded model file; `config/media_assets.yaml` pins the source archives and explicitly allowed extracted filenames. No system PATH or global package installation is required.

## Packages and licences

| Active dependency | Version | Purpose and licence |
| --- | --- | --- |
| sherpa-onnx / sherpa-onnx-core | 2.0.1 | Apache-2.0 local speech runtime; English lexicon frontend |
| opencv-python-headless | 4.12.0.88 | OpenCV Apache-2.0/MIT bindings, LGPL FFmpeg video decoding |
| SoundFile | 0.13.1 | BSD wrapper, bundled LGPL libsndfile 1.2.2; actual FLAC/OGG/MP3 checks passed |
| cffi / pycparser | 1.17.1 / 2.22 | MIT / BSD support libraries |
| Whisper tiny.en int8 | pinned ONNX files | MIT English ASR |
| Kokoro English v0_19 int8 | pinned ONNX/voice/token files | Apache-2.0 English TTS |

Official sources: [Sherpa repository](https://github.com/k2-fsa/sherpa-onnx), [removal of GPL speech frontend](https://github.com/k2-fsa/sherpa-onnx/pull/4055), [OpenCV wheel licensing](https://github.com/opencv/opencv-python), [SoundFile documentation/licensing](https://python-soundfile.readthedocs.io/en/latest/). The exact installed wheel hashes and codec build inventory are retained locally under `.runtime/media_downloads`.

PyAV 16.1.0 was initially downloaded and inspected. Its wheel contained GPL x264/x265 despite individual FFmpeg library version strings reporting LGPL. No recording was decoded with it. All three installed PyAV directories were reversibly quarantined in `.runtime/quarantine_pyav_16_1`, outside the application import path. The application uses OpenCV instead. This is not an approval to use that quarantined GPL build.

## Model downloads

| Archive/file | Actual bytes | SHA-256 provenance |
| --- | ---: | --- |
| sherpa-onnx-whisper-tiny.en.tar.bz2 | 118071777 | `2bd6cf965c8bb3e068ef9fa2191387ee63a9dfa2a4e37582a8109641c20005dd`; first HTTPS download captured locally, no publisher digest was available |
| kokoro-int8-en-v0_19.tar.bz2 | 103248205 | `c9f0dd393615805b0bab050c340834d5e684e732aec91c0e860cd30e982c08bd`; matched upstream release digest |
| lexicon-en-us.txt | 6305773 | `8b67ae549a465eee78f92ecb74644ad90c3c58ce65f19c68baf85878a10ef73a`; matched upstream release digest |

Release URLs and extracted-file hashes are in the YAML configuration. The first-download Whisper pin makes future installs reproducible; it is not independent publisher authentication. Archive extraction selects regular allowed files only, not arbitrary paths, links or bundled phonemizer data.

## Operation and verification limits

From the repository's Python environment, run `python scripts/setup_media.py --verify-only` to validate current readiness. Explicit provisioning is `python scripts/setup_media.py`; it downloads only the pinned open-source wheels and assets, installs with `--no-deps --target .runtime/optional_deps`, validates file hashes, then runs genuine speech and codec probes. `--verify-only --probe` reruns those bounded probes without provisioning. Existing mismatched cached files are preserved and refused. The complete fresh-install command has not been verified on a clean machine or another OS; the installed Windows runtime and individual real model/API paths have been verified.

Workers use two CPU threads, serialize native/provider work, validate loaded hashes, have a 120-second job deadline and terminate/wait before temporary-file cleanup. Audio is limited to 60 seconds, 8–192 kHz, one/two channels and the shared upload quota. WAV integer PCM plus actual decoded FLAC/OGG/MP3 are supported; M4A/AAC is not claimed. Silence produces an explicit error rather than an invented transcript. ASR timestamps describe the whole recording window, not word alignment.

Video validates actual MP4/MOV/AVI/WebM/MKV signatures and decodes at most 60 seconds, 3600 frames and four million pixels per frame, sampling at most three frames. Timestamps come from the decoder; an unavailable timestamp stays unknown. Sampled frames and originals remain separate hashed attachments. Frame interpretations are correlated model inferences from one recording. Video audio is not transcribed; upload the audio separately. The live demonstration clip is explicitly encoded from a licensed still, and proves the processing path rather than real mechanical motion analysis.

Speech is English only. Unknown English terms are spelled out; exact digits are retained and citations are omitted from spoken text. Unsupported non-English text is refused rather than silently dropped. Reply controls generate the first 250 characters explicitly, retain the full displayed reply and expose WAV playback/mute/stop/cancel. Actual recorded-file ASR/TTS and same-chat inference passed; browser microphone permissions/capture and physical speaker playback remain unverified because the supported browser host is unavailable.

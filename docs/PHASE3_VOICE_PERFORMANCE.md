# Phase 3 voice performance and quality

Retained provider: local `sherpa-onnx-2.0.1`, Kokoro English v0.19 int8, voice 0, speed 1. Existing Whisper base.en int8 is the default; existing tiny.en int8 is an explicit faster/lower-accuracy option. No new weights or speech services. The media process retains one heavy engine/profile; changing ASR/TTS frees the old engine and initializes the requested one. Idle eviction is 90s.

## Real fresh synthesis, paired inputs

| Chars | Before total s | After total s | After audio s | Init before / after s | Generate before / after s | Model reused |
| --- | --- | --- | --- | --- | --- | --- |
| 22 | 12.418 | 9.274 | 1.632 | 4.313 / 3.844 | 4.656 / 4.609 | False |
| 26 | 12.180 | 5.667 | 1.979 | 3.609 / 0.000 | 5.078 / 5.157 | True |
| 65 | 17.635 | 10.957 | 4.109 | 3.734 / 0.000 | 10.406 / 10.469 | True |
| 218 | 33.830 | 27.358 | 12.688 | 3.516 / 0.000 | 26.750 / 26.812 | True |

Every listed WAV is real, uncached synthesis with matching pinned model hashes. First after-TTS is model-cold/process-warm following ASR. Later phrases are unseen exact texts with a warm TTS model. Phase timings show the gain is initialization/import reuse; long-text neural generation remains approximately unchanged. Small audio frame-count/hash differences occurred between genuine syntheses; no bit-identical waveform or subjective quality equivalence is claimed. Per-call normalization now reuses a single lexicon parsed from exact pinned bytes; temperature names are explicit and exact numbers remain.

Observed before TTS peak RSS range 433893376–538017792 bytes; after 499130368–568328192 bytes. These are worker lifetime peaks, so retained after peaks include earlier ASR; not per-request/whole-system peaks. Memory retention is a tradeoff, bounded by one media engine and idle eviction.

## Actual sentence-WAV streaming and cancellation

Fresh two-sentence request: first completed WAV **12.881s**, terminal **17.724s**. Exact cached replay: first **0.244s**, terminal **0.422s**. Different warm introductory phrase: first WAV **3.499s**, then deliberate cancellation reached terminal **0.020s** later; actual interpreter child exited. These are received WAV times, not first audible playback. The cancelled request is not reported as a completed speech benchmark.

The existing SSE contract emits complete sentence WAVs, never partial generated waveform frames. Keep each chunk ≤160 characters, ≤10 chunks, existing overall text/voice/speed bounds. Cache is local, bounded to 8 entries/8,000,000 bytes/300s reuse TTL, and keyed by exact input/voice/speed/model/thread/source identity. Cache hits explicitly state no current inference; original synthesis counters stay separately labeled. This is not secure memory erasure. Explicit resident-worker failure produced a real WAV via original one-shot fallback (10.695s; inspect receipt for measured fields).

## Real ASR and separate offline transcription evaluation

| Recording / condition | Reference words | Word edits | WER | Measured latency s |
| --- | --- | --- | --- | --- |
| before_base_pump | 16 | 4 | 0.2500 | 7.183 |
| before_tiny_pump | 16 | 6 | 0.3750 | 5.000 |
| after_final_base_pump | 16 | 4 | 0.2500 | 1.639 |
| after_final_tiny_pump | 16 | 6 | 0.3750 | 2.172 |
| derived_long_recording | 53 | 4 | 0.0755 | 7.884 |
| generated_speech_asr_proxy | 5 | 0 | 0.0000 | Not measured for this proxy |

Fresh ASR happens during audio upload. `audio.transcript` subsequently reads that stored result; its ~0.1s response must not be called recognition latency. Base upload timing includes ingestion; explicit tiny server timing has a different boundary. Same technical recording retained 4/16 word edits for base and 6/16 for tiny before/after: no accuracy gain claimed. Longer 27.671s derived WAV concatenates four original public clips, with original hashes/offsets retained; no evaluator-only causes or text labels enter runtime inference. Spoken cancellation words in a clip remain data and did not execute a control action.

Reference scoring ran in a separate offline process after outputs; public transcription-reference manifest hash is `3b6916ecee2bb08ceff5e5999c3ce8e040b66a829ae64df9c458c0400f5a0af4`. Tiny synthetic sample, not broad industrial/noisy/multilingual accuracy. ASR review/edit remains required. Round-trip generated speech has 0/5 edits, an intelligibility proxy only.

## Human listening and device acceptance

**Not performed:** blind listening/naturalness/pronunciation review, physical microphone and speaker tests, actual echo/noise/barge-in, continuous voice-call UX. Do not relabel PCM/WAV/network tests as physical acceptance. Phase 4 should play randomized before/after WAVs at equal output volume; reviewers should transcribe without seeing the sentence, score intelligibility/technical pronunciation/naturalness separately, log browser/audio device and record audible onset with a loopback measurement. References must stay outside model inputs. No subjective score is invented here.

Backend contracts and playback/cancellation wiring: [Phase 4 handoff](PHASE4_BACKEND_HANDOFF.md).

# SIRE V4.5.1 conversation regression — 2026-11-18

The urgent conversation regression is repaired and the main application restarted on http://127.0.0.1:8000. Reload the browser tab to load the new hashed JavaScript. Physical voice acceptance remains partial; this is not a claim that all original V4.5 release gates are complete.

## Reproduced production causes

Read the production SQLite through a read-only connection and saved a consistent private backup before edits. The live conversation records match the report: Hello? cancelled at7.890s and13.141s, then completed13.781s; the longer voice request completed15.250s. Text SIRE explanations failed22.969s and28.765s; hi failed25.813s. The original failed raw generations were not persisted, so their precise text cannot be recovered retrospectively. A real Qwen replay on a disposable copy of the exact pre-failure history reproduced the same validator error in26.485s. Its raw response invented “Simulated Intelligent Reasoning Engine”, denied implemented SIRE capabilities, and cited [E1]. The existing fail-closed validator correctly withheld that unsupported response. Raw replay/prompt/wire timing is private in .runtime/v45_conversation/raw_reproduction.json.

The defect chain:

- The empty-source compact prompt still instructed the model to use [E1]/[E2]. Voice audio attachments created an actual E1 transcript alias, but later text had an empty reference map.
- Historical evidence IDs, including earlier speech transcripts and failed/cancelled turns, activated evidence-oriented validation/context for unrelated ordinary text. Transcript provenance was treated as independent answer evidence, so equivalent speech/text used different routes.
- A large engineering system prompt, JSON evidence wrapper and uncoupled complete user rows increased ordinary conversational prompt/history overhead. There was no authoritative self-description route, leaving the small model to invent SIRE facts.
- Every speech_started event immediately stopped playback and called chat cancellation. Final transcript submission could also cancel an active turn. Unexpected voice socket closure called the same stop callback. Old logs did not record cancellation origin; they cannot prove whether the two original cancellations were deliberate, feedback, noise, or a disconnect.

## Repairs

New app/chat/conversation.py and config/conversation.yaml choose conservative complete social requests, bounded completed history pairs and transport-independent source semantics. Greetings have a configured deterministic reply; arbitrary ordinary questions still use the real local model. Empty-source prompts never advertise unavailable aliases. Unknown references remain rejected, and numerical/unit/asset/time checks remain active. Citations are optional when there is no supporting external source; fabricated citations are never made valid by this route.

SIRE self-description and hypothesis-engine explanations use exact config/capabilities.yaml text, a hashed resolvable ledger snapshot, and explicit limitations. No invented acronym or fabricated live readiness. Concise spoken variants come from the same authored manifest, while the full source-backed text stays in chat.

ChatRequest.input_audio_id identifies a scoped, actually transcribed recording as input provenance, not independent corroboration. Ordinary typed/transcribed content enters the same route. Explicit audio-analysis requests still use audio evidence. Legacy matching voice-input attachment submissions are supported. Original audio/transcripts and source hashes remain available; provenance explicitly marks ASR unverified/edited.

Voice onset now means candidate speech only. Microphone PCM and late transcripts are suppressed during SIRE playback and a500ms cooldown; deliberate interruption uses Interrupt and speak. This conservative policy does not pretend to identify a human speaker through echo. VAD retains500ms of exact original PCM before detected onset in a bounded30s buffer, recovering short greetings lost by repeated segmentation. Punctuation-only ASR is rejected explicitly. Socket closure no longer implicitly cancels an unrelated response. Controlled cancellation reasons, client control events and provider timing are persisted for future diagnosis.

The real stream-read wrapper now races Stop/deadline before the first model token. A QA timeout-argument mistake in its first implementation was caught by real requests, corrected, and covered by a stalled-read regression before deployment. An early full test run was stopped because a legacy cancellation fixture waited forever for a model call on a greeting that now correctly bypasses it. Model-transport fixtures now use a model-bound story question and bounded waits; old greeting trace expectations were updated to the actual deterministic route. Subsequent286pass/1legacy expectation failure was corrected; final suite is below. All failed attempts are retained.

## Genuine local network results

The exact requests, SSE events, routes, input provenance, evidence, actual tool traces, models and timing are in CONVERSATION_REGRESSION_RESULTS.json and .runtime/v45_conversation/network_retry/results.json. Real speech bytes were replayed from the user’s existing recordings through TCP/WebSocket, Silero and Whisper; no transcript or model response was substituted. TTFT is network-visible checked answer text, not upstream first token or audible playback.

| Case | Actual route / validation | First text s | Chat/request total s | Scope/result |
|---|---|---:|---:|---|
|1_new_hi|fast_conversation / social_no_external_claims|0.078|0.094|complete; actual_network|
|2_existing_hi|fast_conversation / social_no_external_claims|0.062|0.078|complete; actual_network|
|3_what_is_SIRE|fast_conversation / exact_application_documentation|0.094|0.109|complete; actual_network|
|4_hypothesis_engine|fast_conversation / exact_application_documentation|0.094|0.094|complete; actual_network|
|5_voice_Hello_recorded_file|fast_conversation / social_no_external_claims|0.094|0.110|complete; actual_recorded_audio_replay_not_live_microphone|
|6_voice_followup_after_text|fast_conversation / social_no_external_claims|0.094|0.110|complete; actual_recorded_audio_replay_not_live_microphone|
|7_text_after_voice|fast_conversation / exact_application_documentation|0.078|0.093|complete; actual_network|
|8_deliberate_interrupt_network_control|general_chat / conversation_no_external_sources|not produced|0.172|cancelled; physical_playback_unverified|
|9_no_speech_control|voice_VAD_only / VAD only|not produced|4.109|quiet_control_pass_background_noise_unverified; background_noise_unverified_quiet_control_only|
|10_industrial_source_backed_statistics|knowledge_query / exact_uploaded_measurement_statistics|0.875|1.000|complete; actual_network|
|11_plain_model_unseen_question|general_chat / conversation_no_external_sources|16.297|16.313|complete; actual_network|
|12_engineering_general_concept|general_chat / engineering_source_checks|14.469|14.485|complete; actual_network|

The first seven requests made no LLM, retrieval, image or hypothesis calls. Manifest answers have genuine documentation evidence; social responses have no external-evidence schema requirements. Existing failed production history recovered in a disposable in-process copy in0.063/0.078/0.078s for hi/SIRE/hypotheses, without model calls. A final current-build network probe completed hi/SIRE/hypotheses in0.078/0.078/0.094s.

Voice file replay including VAD/ASR/chat took6.328s for Hello? and8.688s for the longer follow-up (the latter measurement includes resource contention). Post-ASR chat was0.110s in both. Test8 verifies deliberate API control; a stronger separate probe waited until Qwen was actually resident, then cancelled in3.078s to terminal state with an empty scheduler afterwards. This is not a physical browser barge-in pass.

Test9 uses the actual supplied digital-silence fixture: no transcript/model turn was produced. There is no labeled noise-only corpus recording; the noisy pump report contains speech. Background noise without speech and actual microphone feedback remain unconfirmed, not substituted with a silence pass.

The industrial CSV response used actual source-derived statistics/citations and all returned exact numerical checks verified. No synthetic industrial data reached NASA inference. Unknown-alias and false-number tests continue to fail closed. The two additional general-model probes intentionally use llm.chat; it is expected there, not an unwanted call. No deep/image/NASA call occurred for ordinary requests.

## Measured remaining latency

The reproducing old request emitted209tokens from397prompt tokens: Ollama load5.635s, prompt evaluation5.329s, generation14.236s. It failed after26.485s. This is a real failed request, not a completed-answer baseline.

The new unseen joke request:201prompt tokens/31generated, queue4.891s, load5.385s, prefill2.671s, generation2.045s; checked first text16.297s/total16.313s. Engineering concept:406prompt/35generated, queue0s, load4.882s, prefill5.627s, generation2.732s; first text14.469s/total14.485s. These are different workloads and not a controlled percentage speedup claim. CPU inference and keep_alive=0 still impose cold-loading cost. The actual resident Qwen allocation reported3186108660bytes and size_vram0; no GPU acceleration claim.

Actual short greeting Kokoro output:14.031s to complete network WAV,68449frames/24000Hz. No first-audible timing is available. Software-authored concise speech avoids reading a whole technical manifest, but cold TTS still misses the interactive speed aspiration. The existing installed-local-browser-voice option remains available when the browser reports local English voices; it was not physically accepted here.

## Verification, preservation and current state

- Backend: python -m pytest -q --tb=short ->287passed/1existing Starlette-AnyIO warning/142.44s. Proof: .runtime/v45_conversation/full_tests_final.log.
- Frontend:13passed/905.5868ms; TypeScript passes;646module Vite build9.78s,801509byte JS, existing size warning. Ruff passes; Black173files unchanged.
- Main API4.5.1, ML/text/vision ready. Loaded source/frontend fingerprint 521419520e72527519dabcab3ac594430b2aeb2d6d044ac3cc6f64810bfb91dd. Served JS/CSS bytes verified; current ChatRequest/CancelRequest/voice schemas verified read-only.
- Source/database/frontend backups saved under .runtime/v45_conversation/; actual user records were never used as a writable test namespace. All15production tables remain exactly equal to the fresh pre-cutover backup, including64messages and14attachments.
-813native files and7956frozen stress outputs match;3original runtime ZIP hashes match. Source/frontend checkpoint ZIP CRC checks pass. No retraining, dependency/model replacement, evaluator access, public deployment or original research cleanup.

Files changed: app/chat/service.py, new app/chat/conversation.py, app/evidence/context.py, app/providers/adapter.py, app/api/main.py, app/voice/vad.py and sessions.py; new conversation/capability YAML and voice policy; Chat/VoiceSession/Voice/speech/client types and new voiceGate.ts; regression tests plus model-bound legacy test fixtures; scripts/conversation_regression_acceptance.py and these reports. Existing V4.5 investigation/prediction/evidence regression suite passes.

## Acceptance limitations and next step

Browser inventory returned “The browser access host is unavailable”. No live microphone permission, audible speaker output, autoplay, real room-noise performance, automatic acoustic user identity, or physical interruption is certified. No microphone/privacy prompt was automated. The safe interruption behavior is explicit Interrupt and speak during playback; input detection alone is not treated as authorization to cancel.

Reload the SIRE tab after restart. Manually check a spoken greeting, text/voice follow-ups, deliberate Interrupt and speak, quiet and real noise-only input. Profile/optimize cold local TTS and open-ended CPU model latency next. Existing wider V4.5 semantic/hypothesis-quality gaps remain documented; this repair does not declare the complete V4.5 platform accepted.

Private detailed proofs: production_trace_audit.json, raw_reproduction.json, network/results.json (failed first QA run), network_retry/results.json, actual_resident_interrupt.json, final_probe.json, full_tests*.log, main_contract.json and preservation_after.json under .runtime/v45_conversation/.

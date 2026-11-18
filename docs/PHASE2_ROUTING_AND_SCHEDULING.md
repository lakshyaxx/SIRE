# Phase 2 routing and scheduling

| User/task | Actual route / provider | Source semantics |
|---|---|---|
| Greeting, including addressed/punctuated greeting | `fast_conversation`, deterministic | No model / no citation requirement |
| What SIRE can do | Exact configured capability manifest | System documentation, no invented project facts |
| Open-ended general text | Existing Qwen text route | Unverified model interpretation; strict source checks if sources supplied |
| Pure request to transcribe attached audio | Actual saved ASR extraction | Input provenance; no second LLM |
| Compound audio analysis request | Existing planner, not pure-transcription shortcut | Relevant tools, actual evidence boundaries |
| Image inspection | `vision.inspect` | Visible/unverified observations, original image provenance |
| Documents | Deterministic extraction + selective local retrieval + existing text reasoning | Exact source/page/cell/row references |
| Video | `video.frames` / `video.inspect` + child vision calls | Real sparse timestamps, unobserved intervals explicit |
| Compatible NASA history | `prediction.run` | Dataset/model/input compatibility checked before preserved worker |
| Deep investigation | Existing background job + hypothesis engine + verifier | Measurements, documents and bounded visual tools as actually supplied |

General greeting handling is configuration-backed and guarded against engineering terms. It handles addressed input generally, not just a special-cased acceptance phrase. Text and transcribed text use the same routing rules; the transcript remains provenance without forcing an evidence-dependent investigation. Existing paired history and source-reference validation stay enabled.

The same `app.providers.resources.SCHEDULER` controls cooperating heavy work across SIRE processes with an OS file lock. Queue/accounting is local to the worker; it is not an interprocess global queue dashboard. Existing launcher sets one loaded Ollama model and one parallel generation. Text/vision can replace each other; neither is assumed simultaneously resident on6GB. Keep-alive120s is bounded; optional embeddings and media run in owned CPU workers with configured thread limits. A blocked CPU child or model call does not monopolize the async request loop.

Source-bearing text uses its own650token completion budget; ordinary conversation retains384 and plain chat160. Voice retains180. Source excerpts are capped at500characters in chat, with truncation metadata; a short second passage from the same document is retained before filling space with more measurement channels. Filename term matches add configured relevance weight2 only to already eligible lexical/hybrid results; exact equipment codes still require body matches. These are source selection rules, not evidence truth scores. Displayed statistics are not unnecessarily repeated by the LLM.

Actual same-conversation greetings during active compound jobs: **0.090s / 0.074s**, no model calls. This establishes responsiveness for those bounded serial cases, not a high-load concurrency guarantee.

Cancellation keys include conversation+request IDs. `/specialists/cancel` cannot cancel another case; active calls and watchers are removed on terminal paths. Child workers/timeouts/Stop release scheduler leases. SSE errors never substitute a plausible answer or dummy audio. Actual active GPU-resident vision cancellation: **0.045s** after cancellation submission; this is distinct from request lifetime. Existing background-job/chat/voice cancellation endpoints remain intact.

Cache boundaries bind source bytes, vision instructions/schema, exact speech text/voice/speed/model hashes/thread/code policy. Stop and model/source integrity checks precede cache reuse. Cached resource counters are labeled original synthesis, not current CPU execution. Missing optional providers fail explicitly; discovery does not download models.

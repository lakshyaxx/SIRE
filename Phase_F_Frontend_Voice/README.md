# Phase F - Frontend and Voice (skeleton only)

| | |
|---|---|
| Status | **skeleton only. No frontend work until Phases A-E are accepted and the Figma design is exported into `design/`.** |
| Depends on | the API contract defined below (implemented by the Phase G gateway), the Figma design |
| Feeds | Phase G (connects UI to the gateway) |

## 1. What happens in this phase (later)
The UI is designed in Figma first, then imported and built as a mobile-first web app that talks to the SIRE gateway. Voice lets someone standing next to a car describe the problem and hear the answer. Until the backend exists this folder only fixes the shape of the work, so the design and the backend agree.

## 2. Screens the design must cover
1. **Capture / upload**: camera capture on mobile, several photos, on-screen guidance (wide shot, close-up, underside) and live feedback from the Phase E quality gate.
2. **Context form**: vehicle (make, model, year as free text), mileage, last services (date / km), when the problem was noticed, symptom checklist, optional sensor file upload.
3. **Live reasoning view**: streamed progress; evidence list; hypothesis cards with posterior bars and an evidence matrix (supports / contradicts / missing).
4. **Follow-up questions**: one question at a time with quick-answer chips, free text and voice.
5. **Result**: root cause, lead-up timeline (cause-chain stages), prevention ("what to do and when"), RUL gauge when available, confidence with "what would change my mind", citations that open the source passage, a prominent safety notice when present.
6. **Case history** and **delete my data**.

Non-functional: mobile-first, accessibility (WCAG 2.1 AA), slow-network and offline states, error boundaries, i18n-ready (English first; Hindi/Hinglish optional later), no analytics by default, EXIF stripped on upload, explicit consent before photos are stored.

## 3. API the frontend needs (authoritative OpenAPI is exported by Phase G to `api_contract/`)
```text
POST /api/v1/cases                     multipart: images[], text, optional sensor file -> {case_id}
GET  /api/v1/cases/{id}                status, evidence, hypotheses, diagnosis, trace_id
GET  /api/v1/cases/{id}/events         server-sent events: progress, evidence added, hypotheses updated, question asked
POST /api/v1/cases/{id}/answers        answer to the current follow-up question
DELETE /api/v1/cases/{id}              delete the case and its photos
POST /api/v1/voice/transcribe          audio -> text
POST /api/v1/voice/speak               text -> audio
GET  /api/v1/health
```

## 4. Voice
- Speech-to-text: an open Whisper-family model run locally (for example faster-whisper); push-to-talk, partial transcripts, English first, Hindi/Hinglish as an optional stretch.
- Text-to-speech: a local open-source TTS with a permissive licence (check the licence of the engine AND of each voice).
- Audio is not stored by default.

## 5. Folder map
```text
Phase_F_Frontend_Voice/
├── README.md   # skeleton brief: screens, API needs, voice, prompt for later
├── design/   # Figma export, design tokens, screenshots (added later)
├── frontend/   # app source (created only after the design is imported)
├── voice/   # speech in and out
│   ├── stt/   # speech-to-text
│   └── tts/   # text-to-speech
├── api_contract/   # OpenAPI file exported by the Phase G gateway + generated client
└── tests/   # UI and contract tests
```

## 6. The Codex prompt (use only when I say `start frontend`)
```text
You are the lead frontend engineer for SIRE Phase F. Do nothing until I say `start frontend`. Preconditions to verify first: Phases A-E accepted in STATUS.md, my Figma export exists in design/, and Phase_F_Frontend_Voice/api_contract/ contains an OpenAPI file (if not, ask me to run Phase G step G2 first, or build against the contract in this README with a typed client and tell me).

RULES: AGENTS.md applies. Real, working code only: no fake data in the UI except in tests that are clearly labelled as test fixtures. Everything shown comes from the API. Accessibility and mobile-first are requirements, not extras. No third-party trackers.

STEPS
F0 `read design`: inventory the Figma export (screens, components, tokens); list gaps against README section 2; stop for my answers.
F1 `choose stack`: one paragraph with a recommendation (default: React + TypeScript + Vite, Tailwind, typed API client generated from the OpenAPI file, SSE for events) and the reasons; wait for my approval.
F2 `scaffold`: project in frontend/, design tokens from design/, routing, API client, error handling, environment config.
F3 `screens`: build the six screens against the real API; streaming progress; evidence matrix; citation viewer; safety notice.
F4 `voice`: push-to-talk, transcription and speech output wired to voice/stt and voice/tts services.
F5 `tests`: component tests, contract tests against the OpenAPI file, accessibility checks (axe), a mobile viewport pass, slow-network pass.
Report with real output after each step, then STOP.
```

## 7. Acceptance checklist (for when the phase starts)
- [ ] Figma design exported and gaps answered.
- [ ] All six screens work against the real gateway; no mocked data shipped.
- [ ] Voice in and out work locally.
- [ ] Accessibility, mobile and slow-network checks pass; tests pass; `STATUS.md` updated.

## 8. What comes next
**Phase G - Final integration** builds the gateway these screens call, wires every earlier phase together, runs the end-to-end evaluation, packages everything and prepares the demo.

### Roadmap
- **Phase A - RUL model training** (`Phase_A_RUL_Training/`): Train and compare eight RUL models on C-MAPSS and N-CMAPSS, one at a time, starting from a LightGBM baseline.
- **Phase B - LLM integration** (`Phase_B_LLM_Integration/`): Local Qwen LLM plus the RUL models as tools: data in, the LLM routes it, the model predicts, the LLM explains using only the model's numbers.
- **Phase C - Knowledge base and RAG** (`Phase_C_Knowledge_RAG/`): Real documents, hybrid retrieval and cited cause-chain cards: the evidence chamber.
- **Phase D - Hypothesis engine** (`Phase_D_Hypothesis_Engine/`): The separate brain: competing hypotheses, expected evidence, matching, scoring, follow-up questions and prevention planning.
- **Phase E - Vision** (`Phase_E_Vision/`): Qwen vision-language perception: photos become structured, calibrated evidence.
- **Phase F - Frontend and voice** (`Phase_F_Frontend_Voice/`): UI imported from the Figma design, plus voice in and out. Skeleton only until Phases A-E are accepted.  **<- you are here**
- **Phase G - Final integration** (`Phase_G_Final_Integration/`): Gateway, model manager, end-to-end tests, full evaluation, packaging and demo.

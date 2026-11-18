# Frontend component audit

The export was source material, not an additional running application. Its proposed service contracts and placeholder gates were inspected before reuse. Layout, typography, brand SVGs, spacing, cards, sidebar, headers, preferences and responsive styles are retained in the canonical `web/`.

| Component / route | Actual implementation |
| --- | --- |
| App / main / AppShell | React19, shared API/preferences providers, Router7; persistent conversation history, actual rename/delete endpoints with existing confirmation |
| Assistant `/`, `/chat/:id` | Delivered identity/starters; retained Chat controller; real selected installed model and same conversation ID |
| Chat | SSE stream, receipts, cancellation, error/retry, citations, tools, background investigation and prediction linkage |
| LiveConversation `/live/:id?` | Same Assistant/Chat + real PCM VoiceSession, manual review fallback and inline local speech |
| NewInvestigation | Actual upload bounds, MIME/suffix handling, extraction receipts, same-conversation durable job submission |
| InvestigationWorkspace | Actual status/poll/cancel, findings, sources, hypothesis order/support/contradictions/unknowns, trace, raw report and PDF export |
| DataEvidence | Real paginated searchable modality library, canonical source lookup, image zoom, CSV cells, document sections, original media and transformation metadata |
| KnowledgeWorkspace | Preserves the full original document-ingest/passage browser at `/knowledge`; discoverable from evidence library |
| PredictiveAnalysis `/rul` | Retained Predictions controller; actual four datasets, native models, history charts, compatible upload, comparison, anomaly and discussion linkage |
| Investigations `/cases` | Actual saved cases and durable jobs with lifecycle/search/pagination, no fake completed rows |
| EngineerWorkspace | Retained scenario controller, explicit asset/cutoff, observed/available timestamps, dependency graph, prior cases, what-if, reports and annotations |
| Models `/models` | Real local specialist availability and retained complete native catalog |
| Settings / SystemStatus | Connected device/preferences and actual capability/health checks; installed readiness distinguished from real inference success |
| SireBrand / SireIdentity / ui | Delivered assets/components and cards; no external font/image dependency |
| AudioPlayer | Retained ReadReply/InlineSpeech over actual text, device/volume preferences and stop behavior |
| Inspector / Trace | Preserved detailed evidence/provenance/model trace; inspector/chart code loaded lazily |

Old URL aliases remain: `/data`, `/predictions`, `/assets`, `/predictive-analysis`, `/investigations`, `/overview`. The hidden duplicate overview redirects to case history. No second development server or unused export is required.

Cleanup and recoverability are documented in `FRONTEND_REMOVED_FILES.md`. Protected model/research/runtime files are excluded from cleanup.

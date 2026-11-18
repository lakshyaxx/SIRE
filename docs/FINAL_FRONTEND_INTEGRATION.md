# Final frontend integration — 2026-11-19

The delivered Figma interface is integrated into the existing `web/` application, using the existing FastAPI, SSE, WebSocket and native inference stack. Application version **4.8.0**, existing API contract **2.0**. Production cutover verified; normal launcher serves the integrated build on loopback port 8000.

## Milestones

| Milestone | Actual outcome |
| --- | --- |
| A: inspect source and real interfaces | Complete; delivered `sire front/` audited against actual `app/`, `web/`, OpenAPI and database formats |
| B: recoverable protection | Git checkpoint reference, original index/patches, both source ZIPs and consistent SQLite backup retained privately |
| C: canonical frontend | Delivered shell, local fonts, branding and responsive design live in `web/`; one normal build/launcher |
| D: real API integration | Real upload receipts, persistent chat IDs, SSE, durable jobs, history, exact source lookup, report export and errors connected |
| E: advanced paths | Retained NASA inference/comparison, scenario replay/what-if, model inventory, real voice session and inline local speech controllers |
| F: regression and browser checks | 346 backend tests, 24 frontend tests, 24 actual network cases, 12 selected native routes and seven offline checks passed; browser observations recorded separately |
| G: consolidation | Original export moved intact into ignored checkpoint; eight unused presentation files retired reversibly; functional knowledge ingestion retained |
| H: local cutover | Verified; see `FRONTEND_INTEGRATION_RESULTS.json` and private `cutover.json`. |

## Fixes reproduced during integration

- The delivered client assumed `/v1/*` schemas that the application does not expose. The facade now uses actual `/api/v1/*` interfaces, plus small read-only presentation indexes. No database migration was added.
- New-conversation upload navigated from a nonce URL to the persisted chat ID and remounted the composer, dropping the first pending receipt. A stable compose epoch preserves that transition; an actual React/router regression exercises pending upload, real receipt ID, duplicate submit and failed-send recovery. Browser rerun completed the image conversation.
- File picker snapshots survive clearing the live FileList. Submitted receipts are cleared only after actual request acknowledgement; rejected submissions retain retry inputs.
- Canonical attachment IDs were read from the wrong nested source object. The adapter now resolves `evidence.pointer.attachment_id`, including sources outside the library's first page.
- Delivered SVGs were served as SPA HTML until `/brand` was mounted. SVG/media byte/type tests cover the fix. SPA index uses `Cache-Control: no-cache`.
- Completed jobs displayed a stale running tool event. Terminal lifecycle state now wins. Event timestamps are shown only when actually recorded.
- Large raw numeric JSON was the default findings text. Typed computed measurements now display asset/channel/baseline/recent/change/count, explicitly rounded to six significant digits; exact windows and values remain in the source record. User JSON is never promoted to computed facts.
- A redundant speech-card metadata fetch produced a false unavailable state. The card now consumes the actual parent summary and retained local speech controller.
- Desktop navigation footer overflow and initial chart payload were reduced: retained inspector/charts load lazily. The tested main bundle is 537.94 kB, lazy chart 327.46 kB; the >500 kB advisory remains visible.

## Preservation

Final fresh verification: **813** native hashes match; **7956** frozen files match; no retired delivered-source mismatch; all **15** original production tables are row-for-row equal before cutover. A copied production database successfully rendered **6** existing saved cases and catalogued **28** attachments through the new indexes. The compatibility exercise used a private copy.

No model retraining, tuning, downloads, protected deletion, paid service, Git publication or public deployment. No evaluator-only files were ingested or used. Synthetic uploads remained in QA; NASA inference used existing compatible saved NASA histories.

## Open acceptance limits

Physical microphone/speaker capture, audible autoplay onset, noise rejection and genuine user barge-in remain unverified. Small local models can produce weak causal proposals or truncate auxiliary check/question strings at configured output bounds; original text and uncertainty are preserved, not repaired with invented prose. Source identity validity is not a causal or citation-semantic accuracy certificate. No universal diagnosis accuracy or real-time/full-duplex claim.

Reports: [component audit](FRONTEND_COMPONENT_AUDIT.md), [API mapping](FRONTEND_API_MAPPING.md), [cleanup](FRONTEND_REMOVED_FILES.md), [voice](FRONTEND_VOICE_INTEGRATION.md), [predictions](FRONTEND_PREDICTION_INTEGRATION.md), [tests](FRONTEND_TEST_RESULTS.md), [readiness](FINAL_APPLICATION_READINESS.md).

Private exact proof: `.runtime/frontend_integration_20261119_005543/`; `.runtime/frontend_integration_current.txt` locates it. Do not publish its databases, user history, model outputs or archived browser profile.

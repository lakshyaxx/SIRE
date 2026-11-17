# V2 confirmed defect audit — 2026-11-17

Current state was inspected, not inferred from the prior report. The live V1 health endpoint returned 200 with ML/Ollama/text/vision availability. `/api/models` returned 44 entries and FD003 assets returned 100 source engines. Git began on main with 38 modified paths, 2,623 pre-existing deleted paths and 3,936 untracked paths. Disk free: 135,427,883,008 bytes.

| Confirmed defect | Evidence | V2 correction |
| --- | --- | --- |
| Ordinary chat is coupled to a NASA engine | frontend/src/main.tsx always attaches its selected model and asset in send(); dataset initializes FD001 | Separate persistent chat service; explicit prediction artifacts only |
| Reply is a fixed report shell | engine/investigation.py returns the fixed summary “Evidence collected from the selected sources.” | Real provider text streaming for ordinary conversation |
| No conversation persistence or CRUD | No conversation database/service/routes in existing API | SQLite sessions/messages/attachments/cases |
| Attachments do not participate in chat | CSV, vision and knowledge are separate screens; chat only sends question/notes/model/source | One attachment-aware composer and evidence pipeline |
| No native streaming or cancel | Existing provider always uses stream:false | Actual provider NDJSON token stream and progressive tool events |
| Hypothesis explanation lacks falsification structure | Only explanation/evidence_ids/missing_checks | Typed hypotheses, expected signs, provenance-checked conflicts and transparent ranking |
| Root remains phase-based | Current config/worker resolves Phase_A_RUL_Training | Consolidated byte-identical native runtime under ml; reversible retirement after parity |

The reported FD001-only behavior is not proven as a backend model defect. The existing UI and API contain all four datasets. Their routing and fresh inference are being rechecked; no fabricated FD002–FD004 failure cause is asserted. The new prediction screen requires explicit dataset/model matching and does not reuse chat state.

The V1 vision HTTP success is only connectivity/schema evidence; generated content was inspected and is limited. V2 preserves visible observations as model-derived evidence, not verified component diagnosis. No probabilities are invented.

## Resolved verification

All four dataset flows were exercised through the new API, and all 168 saved routes actually inferred. Each subset exposes 42 ready routes. No backend FD001-only root cause was established. The chat coupling/fixed-report defects were replaced with persistent real local streaming. Exact evidence and remaining browser limits are in TEST_EVIDENCE.md and V2_RESTART_EVIDENCE.json.

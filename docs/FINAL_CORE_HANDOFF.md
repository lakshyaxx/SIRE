# Final core engineering handoff

## Scope and checkpoint

This handoff reconciles the Abhigyan core/backend directive with the current
repository. The verified starting commit is
`34d41bc46923e1a7d9e089148c3574225aba81fc`. No branch, commit, merge, push,
public deployment, model training, protected-data cleanup or production-state
write was performed in this follow-up.

The implemented application is the V4.5.1 local engineering preview described
by [V45_RELEASE_READINESS.md](V45_RELEASE_READINESS.md). The role directive is
not evidence that a capability exists; current OpenAPI, source, tests and the
linked verification records are authoritative.

## Core ownership map and compatibility

| Area | Canonical implementation | Current contract/evidence |
|---|---|---|
| FastAPI entry and shared API | `app/api/main.py`, `app/api/intelligence.py` | [V45_OPENAPI.json](V45_OPENAPI.json), 58 recorded paths and 0 unresolved local references at the verified checkpoint |
| Orchestration and durable work | `app/orchestration/`, `app/investigation/jobs.py` | One chat orchestrator, typed tool plans, persisted jobs, scoped cancellation/recovery and request deduplication |
| Evidence and claims | `app/evidence/` | Immutable source identities, numerical/unit/asset/time checks, inventory-based absence checks and origin grouping; see [V45_EVIDENCE_VERIFICATION.md](V45_EVIDENCE_VERIFICATION.md) |
| Hypotheses | `app/investigation/` | Retained candidate registry, evidence-based active budget, explicit deferred candidates and heuristic—not probabilistic—ranking |
| Prediction | `app/prediction/`, `ml/registry/catalog.json` | Preserved 168-route catalog; selected LightGBM, ensemble and BiLSTM-attention roles across FD001–FD004 |
| Case memory and what-if | `app/knowledge/case_memory.py`, `app/simulation/` | Scoped comparisons and explicitly simulated counterfactuals; no real-world causal guarantee |
| Local providers/resources | `app/providers/` | Local-only provider discovery and one bounded cooperating heavy-resource lease |
| Voice/media | `app/voice/`, `app/chat/vision.py` | Local final ASR, whole-WAV TTS and bounded video frames; physical browser/microphone/speaker acceptance remains unverified |

Existing V2 callers remain on contract version 2.0. Additive V4.5 interfaces and
exact request/event details are documented in
[V45_FRONTEND_API_HANDOFF.md](V45_FRONTEND_API_HANDOFF.md). Do not infer a
partial-word ASR stream, neural audio-frame stream, calibrated confidence or
verified physical diagnosis from those contracts.

## Follow-up reliability correction

The remaining documented high-severity hypothesis defect was addressed at the
server acceptance boundary:

- `app/investigation/narrative.py` now flags unexpected non-Latin script drift
  in addition to empty text, continuation punctuation, unfinished clauses and
  unmatched delimiters.
- `app/investigation/engine.py` withholds newly proposed malformed mechanisms
  and quarantines malformed inherited candidates during a revision. The full
  original candidate and reasons remain in the round's `quality_rejections`
  trace. The API returns an explicit unresolved/incomplete result instead of
  publishing that text as an accepted hypothesis.
- `tests/unit/test_v3_2_hypotheses.py` covers the previously observed mixed-script
  pattern and proves an unfinished proposal is absent from final hypotheses
  while its original output remains auditable.

This is a reliability validation step, not a prompt-style redesign or a claim
of general semantic entailment.

Two additional directive gaps were corrected after the initial audit:

- `app/evidence/verification.py` now recomputes signed percentage change from
  the exact baseline/recent source windows. Percent claims accept only `%` or
  `percent` as their display unit, retain the source measurement unit, reject a
  zero baseline as insufficient, and interpret explicit decrease/drop/reduction
  wording as a negative sign before comparison. Delta and percent-delta window
  claims are checked from the first baseline contributor through the last
  recent contributor rather than incorrectly using only the recent window.
- `app/knowledge/case_memory.py` and `app/orchestration/workspace.py` now return
  and render real prior-case IDs, selected/prior asset and cutoff context,
  provisional evidence strength, retrieval reason, shared/different mechanisms,
  same-direction observed trends, unit-compatible differing readings and source
  references. An empty time-eligible result is stated explicitly rather than
  reduced to an opaque count.

## Verification and measured results

Current follow-up commands and actual results:

| Command | Result |
|---|---|
| Focused hypothesis, percent-verification and prior-case rendering tests | **14 passed in 1.35s** |
| Direct narrative assertions for unfinished, mixed-script and complete text | Unfinished and `CJK` drift flagged; complete control returned no issue |
| `python -m compileall -q app/investigation tests/unit/test_phase3_quality.py` | Completed with no output/errors |
| `python -m black --check` on the eight specified Python files | **8 files would be left unchanged** |
| `git diff --check` | Completed with no output/errors |

The broader targeted command did not run tests because the documented root
`.venv` is absent. The available Python 3.10 interpreter then failed collection
because `pypdf` is not installed; it also has no Ruff module. An older facility
memory test additionally cannot execute under Python 3.10 because the application
uses `asyncio.timeout`, which requires Python 3.11 or newer. No replacement
environment or dependency was installed. Therefore this follow-up does **not**
claim a fresh full regression or Ruff pass.

The last recorded full application evidence remains the V4.5.1/performance
checkpoint: 293 backend tests passed with one warning in 145.21s, 13 frontend
tests passed, build/static checks passed, 813 native hashes and 7,956 frozen
files verified, and all 15 production tables matched the immediate pre-cutover
backup. Those are retained historical measurements, not rerun measurements from
this follow-up.

A read-only request to the documented loopback service timed out and a second
request could not connect, so no live-route result is claimed. The retained
`docs/V45_OPENAPI.json` parses as OpenAPI 3.1.0 with 58 paths and 24 schemas. It
contains the canonical health, capabilities, chat, attachment, job, evidence,
run-trace and prediction interfaces; parameter names and prediction route names
follow the existing compatible API rather than the directive's candidate route
spellings.

## Preservation, rollback and release limits

No production database, upload, model artifact, protected native file, frozen
stress result or original V2/V3/V3.2 bundle was changed. The correction is
source-only and can be rolled back by restoring the three changed Python files
from the existing source checkpoint; do not use a destructive Git reset over
unrelated user work.

Release acceptance remains conditional. Required external/manual evidence is
still missing for physical microphone/speaker/browser behavior, general
industrial semantic/causal accuracy, approved independently labelled case
evaluation, clean-machine portability and sustained resource qualification.
The current system must continue to label image interpretations, NASA outputs
and what-if results according to their actual provenance and limitations.

## Local operation

The documented launcher is `.\.venv\Scripts\python.exe scripts/dev.py` on
loopback port 8000, but that interpreter is absent in this checkout. Restore the
protected documented environment (without replacing its external dependency
source), then run the full commands in
[V45_FRONTEND_API_HANDOFF.md](V45_FRONTEND_API_HANDOFF.md) before cutting a new
release checkpoint. Do not restart or mutate production merely to validate this
source change; use an isolated state directory and QA port.

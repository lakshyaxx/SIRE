# SIRE FINAL STABILIZATION RESULTS

Release: **CONDITIONAL for a supervised local showcase; not accepted for autonomous engineering conclusions.**

The application is running locally as 4.8.2. This was a bounded stabilization, not a complete resolution of physical reasoning quality. PUMP-101 remains partial after a generated explanation failed review. One genuine-model follow-up is still withheld by numerical verification. Transport completion does not establish semantic correctness; several contextual answers still overgeneralize motor-current behavior and repeat an analogy instead of answering the new question well.

Recorded at 2026-11-18T23:34:48.884152+00:00. Elapsed since the saved checkpoint: 53.10 minutes; this excludes the initial read-only inspection before that checkpoint. The engineering deadline was 2026-11-18T23:39:30+00:00.

## Baseline and recovery

- Branch: `integration`; baseline commit: `174cea7978698606e475c893ee52ef468c7c4dab`; clean working tree at entry.
- Recovery reference: `codex/stabilization-checkpoint-20261119_041142`. No branch checkout, research reset, model training, downloads, dependency replacement, publishing or public deployment occurred.
- Private evidence and checkpoints: `C:\Users\laksh\OneDrive\Desktop\SIRE\SIRE\.runtime\stabilization_20261119_041142`. `source_before.zip` has SHA-256 `c97f1870a015dd9231c47e299959042b79328692a4491ba6fe4de0aa7c8f375a`. `production_before.sqlite3` and `production_cutover.sqlite3` are consistent backups; `web_dist_before` retains the prior built frontend.
- Baseline backend: 370 passed, 1 warning in 191.59 seconds. Baseline frontend: 26 passed, 0 failed. Actual command logs remain in the private evidence directory.
- Final backend: **383 passed, 1 warning in 271.59s (0:04:31)**. Frontend: 27 passed, 0 failed. Black, Ruff, TypeScript/build, `git diff --check`, and `pip check` passed. Build warnings remain about bundle size and dependency module directives; the existing AnyIO deprecation warning remains.

## Changes and reproduced root causes

1. **Incomplete generated text:** concise schema fields were limiting mechanisms and unresolved text to short strings, while prior review checked mechanisms but missed assumptions and unfinished follow-ups. Review now covers generated fields, mixed-language drift and obvious clause fragments. Mechanisms have a bounded 360-character contract; unresolved sentences have a bounded 240-character contract with sentence termination. At most one quality retry is allowed within the existing time budget; rejected fields/candidates stay in diagnostic records and yield an explicit partial result. This does not prove every apparently complete sentence is meaningful.
2. **Source and causal presuppositions:** known unavailable-report assertions and maintenance-date presuppositions are rejected. Unqualified mechanical-to-flow/pressure chains and unsupported stability statements receive bounded review. A missing test cannot exclude a cause. These are conservative controls, not a general physics verifier; remaining qualitative overclaims are listed below.
3. **User-only evidence:** the source compactor previously discarded the sole user claim when it duplicated the question. It now retains a real alias for that report while keeping its reliability low and its identity unverified. Hypothesis generation can cite the actual hypothetical report without manufacturing corroboration.
4. **Missing FAN channels:** the explicit wide-CSV configuration omitted airflow, speed and inlet-filter differential pressure. All six named channels are now mapped with declared units. Empty measurements retain their source row/field/timestamp and are not imputed. Model-facing numeric context is compacted without changing the immutable source records.
5. **Recommendations:** channel availability now distinguishes interpreting supplied readings from collecting new measurements or independently confirming them. Additional pressure-drop aliases cover the observed FAN wording. This does not certify that the existing resolution is adequate for every diagnostic test.
6. **Asset scope:** unselected multiple measurement assets require a selection; a named asset excludes other known measurement assets from model context. Source-declared identity and requested identity remain unverified. Network PUMP/FAN cases retained their requested assets; permanent tests cover ambiguous and unrelated assets. No silent default-equipment substitution was introduced.
7. **Project knowledge:** authored capability documentation covers actual orchestration, hypotheses, evidence, media, memory and compatible NASA prediction functions. Completed topic metadata supports short contextual follow-ups. This route does not provide engineering diagnoses or pretend to be model inference.
8. **General conversation regression:** real novel questions exposed a 160-token plain-response limit and a planner that treated the noun “investigation” as a new analysis request. The plain budget is now bounded at 384 tokens with a concise-answer instruction. General causal questions without a selected source/asset stay conversational; explicit investigation and revision actions remain available. Follow-up model context includes this conversation's actual saved case, requested asset and ranked unverified possibilities. A different explicitly named asset and explicit requests without source evidence do not borrow that case. No test-question answers or phrase-specific novel-question routes were installed.
9. **Frontend reliability:** terminal job state cannot be replaced by an older/running poll; terminal displays suppress stale running-tool labels. The backend emits the actual hypothesis-engine terminal event. Duplicate source IDs are deduplicated, duplicate locator text is reduced, long observations are explicitly excerpted with the original available, observation provenance is labeled, empty technical details are hidden, and duplicate persisted chat-error display is reduced. Full source and trace records remain available.

Changed application areas: `app/chat`, `app/evidence`, `app/investigation`, `app/orchestration/planner.py`, `app/api/main.py`, the existing YAML policies, and the existing chat/investigation frontend. Permanent regression additions are `tests/unit/test_final_stabilization.py` and `web/tests/stabilization.test.mjs`.

## Original-case acceptance and latency

The original application-stored FAN files were copied into a disposable namespace. The image is the original stored normalized image, not a claim to have recovered the pre-upload camera bytes. CSV/PDF hashes and original attachment IDs are retained in `fixture_checks.json`, `baseline.json` and the machine-readable results. No evaluator-only material was read or ingested.

| Case | Fresh baseline | Final | Final job state | Retained mechanisms | Status poll median / maximum |
|---|---:|---:|---|---:|---:|
| FAN-042 | 17.630 s | 33.237 s | complete | 2 | 0.0094 s / 0.2452 s |
| PUMP-101 | 11.350 s | 40.926 s | partial | 2 | 0.0088 s / 0.0143 s |

These are actual client wall times, with polling overhead. Final runs overlapped the regression workload; they are not controlled isolated latency benchmarks. The quality retry and broader evidence coverage increased investigation latency compared with baseline. The increase is recorded, not presented as a speed improvement. An investigation job can finish its pipeline while its proposed causes still require review.

- FAN: independently reread **24 rows**, verified all **6 channel summaries** and **143 numeric records** against first-24/recent-6 arithmetic. Vibration has 23 numeric records and the missing sample at 2026-11-18 14:00 UTC remains missing. The PDF's conflicting WO-611 / TECH-121 accounts remain unresolved. Images stay unverified observations and cannot establish internal wear.
- PUMP: hypothetical user values remain source reports, not sensor measurements or NASA inputs. Two competing mechanisms were retained; rejected explanation text caused an explicit `hypothesis_quality_review` partial result. No confirmed root cause or RUL was generated.
- All 5 distinct support/conflict references in the final retained reports resolved through the real evidence endpoint. **This is reference resolution, not a semantic support success rate.** Schema-only or indirect evidence can still be proposed for a mechanism; such associations require engineering review.
- Actual browser submission uploaded the three FAN files, navigated to a durable job and completed. A deliberate overlap first produced the real bounded queue-capacity rejection; retry retained the files and completed. Browser snapshots show final source statistics, provenance, explicit partial errors and actual execution traces. The initial fresh-upload browser run preceded the last backend tuning; final stored-file requests and final findings pages were checked against the final backend.

## Generalization: genuine Qwen, separate from documentation

The final 12 capability/social turns completed in 86.0–127.3 ms. These are authored-documentation/social results and must not be used as LLM latency claims.

The following sequential requests used actual `qwen3:4b-instruct`. The first four form a new conversation; the last four follow the actual saved PUMP-101 investigation. All had empty tool lists: no new investigation, vision, prediction or search was invoked. Full answers, real source maps, provider metrics, evidence schemas and traces are retained in `generalization.json`; the earlier failed runs remain in `generalization_attempt1.json` and `generalization_attempt2.json`.

| # | Actual question | Route | Result | Total seconds | First validated text seconds |
|---:|---|---|---|---:|---:|
| 1 | Why might a centrifugal pump vibrate more even if its operating speed stays constant? | plain_conversation | complete | 3.812 | 3.8106028999973205 |
| 2 | If temperature rises but vibration stays stable, what would you check first and why? | evidence_conversation | complete | 7.419 | 7.417869099997915 |
| 3 | What if the airflow decreases immediately after maintenance? | plain_conversation | complete | 1.933 | 1.931679699999222 |
| 4 | Explain the difference between evidence supporting a hypothesis and proving it. | plain_conversation | complete | 1.670 | 1.669120999998995 |
| 5 | I don't understand the second possibility. Explain it using an everyday analogy. | evidence_conversation | complete | 4.315 | 4.31417629999487 |
| 6 | What information from our last investigation would change your conclusion? | evidence_conversation | complete | 4.055 | 4.053326199995354 |
| 7 | Can two separate faults explain the observations better than one? | evidence_conversation | complete | 4.056 | 4.054305300000124 |
| 8 | What would make you reject your leading hypothesis? | evidence_conversation | error | 20.584 | withheld |

7 of 8 responses completed without an output-limit error; one was withheld for `unsupported_numeric_claim`. This is **not** a 7/8 reasoning-accuracy score. The analogy/current reasoning remains overconfident and later answers sometimes repeat it. No prior physical inspection, alignment history, pump curve or frequency threshold is established by these user reports. The failing response was withheld rather than delivered as a verified answer. No broad generalization acceptance is claimed.

Provider time-to-first-token is separately recorded from first validated text; buffering intentionally delays user-visible text until validation. Queueing, prompt token count, prefill, generation count/duration, load duration and validation duration remain in the actual metadata. The first novel question, for example, had 143 prompt tokens and 65 generated tokens; queue time was 2.266 seconds. A simultaneous test workload contributed contention. No guaranteed subsecond voice or general-engineering response is claimed.

## Runtime, protection and recovery verification

- Actual Ollama residency during inference reported Qwen 4.0B `Q4_K_M`, context 4096, `size_vram` equal to model size (3,180,247,121 bytes). NVIDIA inspection observed the RTX 4050 Laptop GPU under inference load. `ollama ps` later showed no resident model after expiry; it is not evidence of CPU fallback. No additional model was downloaded. Actual provider load/prefill/generation metrics are saved; a controlled full application cold-boot study was not performed.
- **12 actual selected FD001–FD004 routes passed**, covering low-latency, ensemble and deep selected models over genuine compatible saved NASA histories. Synthetic FAN/PUMP data was never fed into those predictors. Per-route values/model identifiers/times remain in `native_routes.json`.
- Guarded local runtime checks passed for text generation, embeddings, actual Kokoro WAV synthesis, ASR of that synthesized WAV, genuine native inference, refused nonexistent loopback service, and denied external Python DNS. This is a real TTS-to-ASR file round trip, not human microphone acceptance or an OS-wide air gap.
- Actual QA HTTP missing-attachment submission returned 404; an actual newly submitted job was cancelled and persisted as `cancelled`. Worker exceptions, citation rejection, unit safety, source scope and restart behavior also retain regression coverage. A live native worker crash and a production provider outage were not injected in this window.
- Read-only preservation comparison found **all 15 production tables identical in row content by canonical digests**, before and after the normal-launcher restart. **813 native files** verified and **7956 frozen files** had no mismatches. Full row data was not copied into public documentation.
- The normal `scripts/dev.py` launcher now serves 4.8.2 at `http://127.0.0.1:8000`. The served index exactly matches the staged build, and the production namespace matches `.runtime/v2/sire.sqlite3`. QA records remain separate.

## Observable quality rubric

No invented numerical quality score is assigned. The criteria below make the verified scope and failures reviewable. A valid source ID is never counted as proof of the physical mechanism.

| Dimension | Observable criterion | Assessment |
|---|---|---|
| Numerical source accuracy | Independent CSV first24/recent6 arithmetic agrees for all mapped channels; missing source values are not imputed. | verified for fixture statistics only |
| Evidence correctness | Cited records resolve and actually support the stated observation/relationship. | partial: reference resolution checked; model support relationships can still misuse schema or indirect evidence |
| Asset/time consistency | Explicit requested asset retained; unrelated measurement assets excluded; historical sources respect cutoff. | asset checks verified; broad historical network matrix not rerun |
| Hypothesis relevance | Retained mechanisms relate to supplied observations without forced padding. | tentative, requires engineering review |
| Mechanism completeness | No observed terminal fragments, language drift or mismatched delimiters in accepted fields. | bounded textual review verified; not a full semantic proof |
| Causal restraint | No unsupported physical connection stated as established. | partial: rejected candidates withheld, but broad causal validity remains unverified |
| Contradiction handling | Conflicting original maintenance accounts retained without picking a true account. | final maintenance conflict retained as unresolved; broad hypothesis-conflict semantics unverified |
| Missing evidence | Missing CSV sample retained; existing channels distinguished from absent tests. | verified source inventory; model adequacy claims need review |
| Diagnostic usefulness | Checks refer to relevant missing discriminators or qualify re-use of supplied readings. | qualified recommendations; real-world usefulness unvalidated |
| Clarity | Concise, readable, complete answers with explicit uncertainty. | mixed; fast documentation clear, general reasoning needs human review |

## Remaining gaps and prioritized next work

1. Release blocker for autonomous diagnostic use: semantic support and physical causal reasoning remain unreliable. A causal claim can have a resolvable citation without that citation supporting the mechanism. Investigate the saved counterexamples before claiming broad fault-diagnosis accuracy.
2. Resolve the final rejection/falsification follow-up that introduced an unverifiable quantity. The standard service did not persist its withheld raw streamed prose; capture that text in isolated QA before diagnosing the exact rejected span. The transport did not truncate it; verification withheld it. Retain strict numeric checks rather than declaring this test passed.
3. Improve contextual specificity and avoid recycling an earlier analogy as the answer to a different question. The actual conversation/asset is now supplied, but prompt instructions alone did not achieve reliable reasoning.
4. Reduce investigation retries and model-switch load without sacrificing review. The final evidence-rich runs were slower than the fresh baselines. No architecture redesign or new model is required to inspect the captured timing breakdown.
5. Broader conflicting-equipment/what-if/prior-scenario explanation acceptance was not rerun end to end; existing regression coverage passed. No new what-if or scenario-comparison implementation is claimed. Physical microphone, speaker feedback, deliberate audible interruption, background-noise acceptance, phone-browser use and broad industrial diagnostic validity remain unverified.

No additional input is needed for the completed reversible changes. A separate bounded pass should address the saved reasoning failures before an unsupervised demonstration.

## Rollback

Stop only the verified local launcher after confirming no active jobs. Restore only the changed application/config/frontend source paths from `codex/stabilization-checkpoint-20261119_041142` (or the verified source ZIP), and restore the prior built frontend from `web_dist_before`. Review the diff first; do not hard-reset the repository or remove unrelated user changes. Restart with the root `.venv` and `scripts/dev.py`. **Do not replace the live database with a checkpoint backup:** that could erase later user records. Models, frozen results, dependencies and research require no rollback because they were not changed.

Machine-readable measured results: [FINAL_STABILIZATION_RESULTS.json](FINAL_STABILIZATION_RESULTS.json). Detailed private transcripts, original fixture IDs, raw structured model responses, screenshots, command logs and backups are in the directory above.


## Final synchronization check

A final saved-case evidence-event/metadata synchronization correction keeps the frontend source list consistent with the exact sources sent to Qwen. The full 383-test suite preceded that small correction; 35 relevant regressions passed afterward, including source-event and cross-asset controls. The full suite was not repeated after it. Black/Ruff passed. The normal launcher was restarted again, production 4.8.2 and exact served static bytes were rechecked at 2026-11-18T23:38:37.457508+00:00, and all 15 production table contents remained identical. The application remains running; the disposable QA server was stopped.

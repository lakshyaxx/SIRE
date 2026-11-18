# Phase 3 hypothesis quality and evidence limits

The engine still compares bounded candidate explanations against actual case evidence; it does not certify a hidden physical failure. Generated photo observations remain observations, with synthetic/generated-image provenance, and cannot establish unseen internal damage. Existing native RUL predictions retain their simulated-NASA scope and are not physical-failure proof.

Changes in `app/investigation/engine.py`, `narrative.py` and `orchestration/case_context.py`:

- Equal support preserves evidence/model order rather than sorting by arbitrary hypothesis ID. Incomplete prose receives a secondary tie penalty, not a fabricated probability.
- Empty mechanisms, unfinished clauses/delimiters and trailing continuation punctuation are explicitly flagged. `quality_status` is `incomplete_text` or `complete_text_unverified`; complete prose does not establish truth.
- Claims that a recorded channel is missing are checked against actual inventory. Contradicting mechanism/assumption candidates are withheld with source-derived availability checks; no invented replacement explanation is inserted.
- Diagnostic checks and source support are reported explicitly. Proposal/display coverage is bounded (2 new model proposals, 8 displayed candidates), with deferred registry entries retained.
- Old saved text is reviewed at display time under current completeness rules without rewriting historical records.

Existing `proposal_schema.expand` already restores and validates known aliases across mechanism, assumptions, missing tests, predicates and unresolved queries. This phase added regression coverage; it did not newly invent that existing protection. Unknown aliases remain rejected. Numeric, attachment-integrity, as-of and provenance tests remain active; citation identity alone does not prove semantic support. No validator was globally disabled, no extra repair/planning model calls were introduced.

## Actual final-model outputs

| Actual hypothesis ID | Quality status | Diagnostic checks | Observed text issues |
| --- | --- | --- | --- |
| HYP:73a9259a138b46ea | complete_text_unverified | 2 | None detected by bounded structural review |
| HYP:57028064ba333da7 | incomplete_text | 2 | Mechanism ends with continuation punctuation; explanation may be incomplete. |

The final fresh model still produced one mechanism ending with a comma. The system correctly flags it; the generation defect is not declared repaired. Another mechanism is structurally complete but causally unverified. Final reference IDs all belong to the actual returned case evidence. This is structural/reference acceptance, **not** an independent semantic entailment, top-1/top-3 cause accuracy or false-positive score. Such metrics remain unmeasured; no ground-truth labels were used or fabricated.

Before/after multimodal cases completed with genuine traces and protected native inference outputs are compared in [benchmarks](PHASE3_BENCHMARK_RESULTS.md). A broad no-regression claim about real-world diagnostic accuracy is not justified by these small synthetic integration cases. Independent engineering review is still required before treating hypotheses as maintenance conclusions.

Prioritized remaining work: independently review candidate-to-evidence semantic support; assess truthful conflict/absence handling across more cases; evaluate short-model prose completeness using approved held-out observation-only fixtures; conduct human technical review without feeding evaluator truth into the engine. Preserve frozen stress results.

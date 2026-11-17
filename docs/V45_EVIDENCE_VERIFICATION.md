# V4.5 evidence verification

The ledger preserves source type, attachment/source IDs, original/stored content hashes, source locator, unit, source-declared asset, observed time and availability time. Parsed uploads remain untrusted data, never agent instructions. Sanitized images have distinct original and stored hashes. Audio transcripts and visual observations are model-generated interpretations linked to original bytes.

## Deterministic checks

`POST /api/v1/evidence/verify` requires the selected conversation and typed claims. It recomputes timestamped values and descriptive statistics from source rows. A valid citation cannot establish a wrong number, wrong unit, wrong asset or future-visible value. Claims distinguish direct observation, derived statistic, estimate, interpretation and confirmed finding. Contextual quotation support is separate from causal proof.

Historical investigations fence initial and follow-up evidence by observed/available clocks before the model prompt. Revisions inherit scope and reject explicit changed assets/cutoffs. Runtime job status in a historical context excludes post-hoc intermediate facts. Existing scenario temporal protections remain in place.

The new inventory reads only good-quality finite immutable source rows. Model-generated quantities cannot establish channel availability. Explicit missing/unavailable-channel claims are checked against this inventory and corrected when contradicted; sufficiency/diagnostic adequacy remains unverified. Wrong-asset rows do not prove presence for the target asset. Alias matching is conservative; it is not a complete natural-language entailment engine.

Identical measurement content uploaded as CSV and JSON shares a semantic origin hash. Source formatting and filenames cannot multiply independent evidence weight. Visual origins use sanitized image content (video frames share their parent origin). Unknown asset association prevents sensor/image or NASA/photo linkage from counting as support.

## Actual checks

- Real HTTP source controls: correct source sample verifies; an intentionally different value and unit are contradicted; unrelated asset and an earlier knowledge cutoff never verify; another conversation receives404. Exact IDs/rows/results: `.runtime/v45/network_acceptance/results.json`.
- Final frontend PDF/DOCX/XLSX quote responses: every returned excerpt was searched in the actual resolved source text. This is a targeted excerpt-support check, not general model-narrative certification.
- Final generated-photo case `6e738cbc7a07480bb9403ec74e5380c8`: model incorrectly asserted no recent vibration/temperature data. The absence checker contradicted it using250actual good vibration rows and retained the original claim/check in the case. It did not declare the suggested mechanical cause confirmed.
- The earlier copied V4 case inventory probe checked11actual channels without changing its historical answer or original DB.
- Backend negative controls also cover false point versus mean, model-generated photo versus confirmed failure, historical initial/follow-up leakage and unrelated measured predicates.

Unverified: general semantic correctness of arbitrary prose, sensor authenticity/calibration, physical association, diagnosis or top-1/top-3 accuracy. No evaluator-only material was opened or sent to a model/tool. Known-cause/FPR metrics remain unavailable; no proxy score substitutes for them.

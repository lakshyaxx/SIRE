# Phase 2 multimodal evidence

The corpus is synthetic test input, never replacement NASA research. Only public input fixtures were read. `evaluator_only` was not read/ingested; no cause labels were supplied to inference, logs or embeddings. Audio transcription-reference comparison ran after ASR outputs in a separate evaluator and used only public speech references.

Evidence flow: owned attachment → exact byte SHA/size check → deterministic extraction / actual local model observation → original locator + canonical source/evidence identity → scoped Runner trace → existing claim checks. `read_verified` runs before source interpretation and relevant cache hits. Stored text chunks are re-extracted from the original bytes and checked against their recorded hash/locator before indexing or return. Replaced bytes/forged excerpts are withheld, not repaired by invented text.

| Output | Meaning / boundary |
|---|---|
| Image/photo description | Model observation, authenticity unverified. A visually generated photo is not a verified physical inspection. Photo/schematic/plot classification retained; hidden fault not proven. |
| Video frame | Existing decoder position/timestamp and frame identity, interpreted through the same VLM. Three sampled frames do not cover all events. |
| ASR transcript | User input provenance, not factual corroboration of the assistant's engineering response. Audio hash/model retained, confidence unknown. |
| Kokoro WAV | Actual generated output with hash/sample count/model/voice/speed; not an evidence source. |
| Document excerpt | Original text and page/paragraph/cell offsets, source authenticity unverified. Retrieved instructions remain untrusted data. |
| CSV/XLSX statistics | Actual code computation; formula/nonfinite/non-numeric cells excluded; no inferred unit/asset identity. |
| NASA prediction | Saved native model estimate from compatible original sample; uncertainty/limitations remain estimates. |

Canonical `SRC:`/`EV:` ledger entries and compatible chunk aliases stay resolvable. Source-reference formatting is only an identity check. Exact value/unit/time checks are separate from qualitative narrative entailment and physical truth; responses explicitly label the latter unverified. Neither model fluency nor similarity is verification.

Actual equivalent CSV and JSON measurements have matching `measurement_content_sha256` and **1 retained duplicate origin group** in the compound report. Duplicate formatting does not create independent corroboration. The photo+PDF+CSV+JSON and video+sensor jobs completed with their original source IDs and traces.

Actual verification controls, in order: **verified_exact, contradicted, contradicted, insufficient_evidence, insufficient_evidence** for valid mean, deliberately wrong value, wrong unit, wrong asset, and historical cutoff before source availability. Deliberately incorrect assertions are negative controls, not invented measurements. Historical retrieval filters availability before embedding; the real three-document cutoff test returned zero future passages. No implicit unit conversion or cross-asset match is accepted.

Conflicting handover documents are retained as separate accounts; authoritative maintenance records are required to resolve them. The final real sensor+handover answer completed in17.568s, quoted OperatorA and OperatorB with their separate source IDs, and kept completion unresolved. Independent post-response checks returned `supported_contextually` for both quoted statements. This is two exact-quote checks, not a general semantic-support or causal-accuracy percentage. General qualitative conflict/causal adjudication accuracy remains partial. Conservative mechanism fragment/unmatched-delimiter flags require review; they do not certify completeness or causality.

Limitations: original source authenticity, asset association without explicit metadata, generated photo validity, noisy speech, qualitative entailment and calibrated causal confidence. No field-engineering safety approval follows from this test corpus.

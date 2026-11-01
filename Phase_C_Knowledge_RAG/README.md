# Phase C - Knowledge Base and RAG (the evidence chamber)

| | |
|---|---|
| Status | not started (tracked in `STATUS.md`) |
| Depends on | nothing for the build; the LLM client from Phase B is used for card extraction |
| Feeds | Phase D (retrieval + cards), Phase E (component and symptom taxonomy), Phase B tools (maintenance knowledge) |

## 1. What happens in this phase
The hypothesis engine needs real knowledge to reason with. This phase builds it from **real documents only**:

1. Ingest documents with full provenance (source, page, licence).
2. Chunk and index them for hybrid retrieval (dense + sparse) with reranking and citations.
3. Turn retrieved knowledge into structured **cause-chain cards**: symptom -> failure mode -> root causes -> lead-up conditions -> indicators -> prevention, every field citing the chunks it came from.
4. Evaluate retrieval with real questions and real gold passages.

Nothing is written from memory into the index or the cards. A card field without a citation is rejected.

Scope. Domain 1 (first): automotive engine bay: fluid leaks (engine oil, coolant, transmission, power steering, brake), seals and gaskets, belts and hoses, cooling system, lubrication and crankcase ventilation, filters, overheating and its consequences. Domain 2: turbofan / industrial degradation and maintenance, starting with the NASA "Damage Propagation Modeling" paper that ships with the C-MAPSS download. Document types: owner's and service manuals you own, technical service bulletins and complaint records published by regulators (for example NHTSA), NASA technical reports, open-access failure-analysis and maintenance papers, standards summaries you may use. Put a note in `corpus/_licences/` for every source.

## 2. Contracts provided to later phases
- `retrieve(query, filters, k) -> [Passage{chunk_id, text, score, source_id, title, page, section, domain, component_tags}]`, `get_chunk(chunk_id)`, `search_cards(component, symptom, domain) -> [Card]`, exposed as a Python API and a small FastAPI service.
- `FailureCard` (JSON, pydantic-validated, schema exported to `knowledge_cards/schema.json`):
```text
FailureCard {
  id, domain, component, symptom_signatures[], failure_mode,
  root_causes[ { cause, lead_up_stages[ {order, description, condition} ],
                 typical_indicators[], indicator_channels[] (sensor channels, if documented),
                 diagnosticity {value, basis}, base_rate {value, basis} | null,
                 source_chunk_ids[], strength: "documented" | "inferred" } ],
  prevention[ {action, interval_or_trigger, source_chunk_ids[]} ],
  urgency_note | null (with source),
  scope (vehicle / system the statement applies to),
  evidence_to_confirm[], evidence_to_exclude[],
  status: "draft" | "checked" | "approved", created_by, reviewed_by
}
```
Rules: `base_rate` stays null unless a source states one; `inferred` strength is allowed only with a written justification and is never treated as documented by Phase D.

## 3. Folder map
```text
Phase_C_Knowledge_RAG/
├── README.md   # prompt, schemas and checklist for this phase
├── corpus/   # source documents you add (PDF/DOCX/HTML are git-ignored)
│   ├── automotive/   # engine bay: leaks, seals, gaskets, belts, cooling, lubrication
│   ├── turbofan_industrial/   # turbofan / industrial degradation and maintenance
│   └── _licences/   # one note per source: origin, licence or permission
├── ingestion/   # document parsing, OCR fallback, metadata, ingestion report
├── index/   # vector store files (rebuildable, git-ignored)
├── retrieval/   # hybrid search, reranking, citations, API
├── knowledge_cards/   # structured cause-chain cards with citations
│   ├── drafts/   # LLM-extracted, unverified
│   ├── checked/   # passed automatic claim verification, waiting for human review
│   └── approved/   # human-approved: the only cards Phase D may treat as documented
├── eval/   # questions with gold passages, metrics, reports
├── configs/   # chunking, embedding, retrieval settings
└── tests/   # pytest
```

## 4. The Codex prompt (paste once at the start of Phase C)
```text
You are the lead engineer for SIRE Phase C: the knowledge base ("evidence chamber") that the hypothesis engine will query.

RULES
1. AGENTS.md applies. Real documents only: everything in the index and in the cards must come from a document I placed in corpus/ (or one you downloaded from an open, legally usable source that I approved). Never write knowledge from memory into the index or the cards.
2. Provenance everywhere: every chunk keeps source_id, title, document type, page/section, language, licence/permission note and a stable chunk_id. Every card field cites chunk_ids.
3. Prefer permissive licences for libraries; flag any AGPL/GPL dependency (for example PyMuPDF) and ask before using it. Open-source models only, run locally.
4. Honest evaluation: real questions, real gold passages, report failures.
5. Deterministic and rebuildable: configs in configs/, pinned requirements, fixed ids, one command rebuilds the index from corpus/.
6. One step per instruction, tests first, report with real numbers, then STOP.

STEPS
C0 `setup rag`: environment; choose and justify a local vector store (Qdrant local mode or Chroma); choose an embedding model (BAAI bge-m3 or an equivalent multilingual open model) and a reranker (bge-reranker-v2-m3 or equivalent); verify each loads and measure speed and VRAM; write configs/.
C1 `build ingestion`: PDF text with layout (pdfplumber or pypdf), OCR fallback for scanned pages (Tesseract or docTR), DOCX, HTML, plain text; metadata extraction; de-duplication; language detection. Produce ingestion_report.md listing every file, pages, characters per page, OCR share and failures. Never silently drop a file.
C2 `build index`: structure-aware chunking (target 300-500 tokens, 10-15% overlap, headings and tables kept intact), stable chunk ids (hash of source + position + text), dense and sparse vectors, metadata filters (domain, component, document type), full rebuild command.
C3 `build retrieval`: hybrid search (dense + sparse with reciprocal-rank fusion), optional reranker, filters, passages with scores and citations; Python API and FastAPI service as in the README contracts.
C4 `build cards`: card extraction with the local LLM (client from Phase B): for a (component, symptom) topic retrieve passages, fill the FailureCard schema with JSON-schema constrained output, require chunk citations and short supporting spans for each claim. Verifier pass: for every claim check that the cited chunk text actually supports it (NLI cross-encoder or a strict LLM judge); claims that fail are removed or the card is rejected with a logged reason. Drafts go to knowledge_cards/drafts/, verified ones to checked/. Only I move cards to approved/ (provide a small review script that shows each claim next to its cited passage).
C5 `build eval`: eval/qrels.jsonl {query_id, query, domain, gold_chunk_ids, answerable}. Draft candidate questions from the documents for me to approve; only approved questions count. Include unanswerable questions. Metrics: recall@1/3/5/10, MRR@10, nDCG@10, abstention precision on unanswerable questions, latency. Ablations: dense only, sparse only, hybrid, hybrid + reranker.
C6 `report`: eval/REPORT.md with real numbers, failure analysis (10 real misses with the reason) and corpus coverage (documents, chunks, cards by domain and status).

Reply "Phase C ready" with a 6-line plan for C0 and wait for my command.
```

## 5. Order of work
`setup rag` -> `build ingestion` -> `build index` -> `build retrieval` -> `build cards` -> `build eval` -> `report`. Add documents to `corpus/` at any time; rerun ingestion and index.

## 6. Acceptance checklist
- [ ] At least the NASA damage-propagation document plus a first set of automotive documents ingested; `ingestion_report.md` lists every file and its extraction quality.
- [ ] Index rebuilds from scratch with one command; chunk ids are stable between rebuilds.
- [ ] Retrieval API and service work and return citations; recall@k, MRR and nDCG measured on at least 50 approved questions (including unanswerable ones); ablation table included.
- [ ] Cards: schema validated, every claim cited, verifier results logged, and at least a first batch of cards reviewed and moved to `approved/` by you.
- [ ] `eval/REPORT.md` with real numbers and failure analysis; tests pass; `STATUS.md` updated.

## 7. What comes next
**Phase D - Hypothesis engine** is the separate brain. It takes evidence (user text now, photo findings later, RUL outputs from Phase B), retrieves cards and passages from this phase, generates competing hypotheses, predicts what other evidence each one implies, matches, scores, asks the best follow-up question and plans the prevention step.

### Roadmap
- **Phase A - RUL model training** (`Phase_A_RUL_Training/`): Train and compare eight RUL models on C-MAPSS and N-CMAPSS, one at a time, starting from a LightGBM baseline.
- **Phase B - LLM integration** (`Phase_B_LLM_Integration/`): Local Qwen LLM plus the RUL models as tools: data in, the LLM routes it, the model predicts, the LLM explains using only the model's numbers.
- **Phase C - Knowledge base and RAG** (`Phase_C_Knowledge_RAG/`): Real documents, hybrid retrieval and cited cause-chain cards: the evidence chamber.  **<- you are here**
- **Phase D - Hypothesis engine** (`Phase_D_Hypothesis_Engine/`): The separate brain: competing hypotheses, expected evidence, matching, scoring, follow-up questions and prevention planning.
- **Phase E - Vision** (`Phase_E_Vision/`): Qwen vision-language perception: photos become structured, calibrated evidence.
- **Phase F - Frontend and voice** (`Phase_F_Frontend_Voice/`): UI imported from the Figma design, plus voice in and out. Skeleton only until Phases A-E are accepted.
- **Phase G - Final integration** (`Phase_G_Final_Integration/`): Gateway, model manager, end-to-end tests, full evaluation, packaging and demo.

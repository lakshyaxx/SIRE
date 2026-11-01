# SIRE

**SIRE** is an agentic, multimodal diagnosis system. You give it a photo of a problem (an engine bay, a leaking oil pan, ...), the maintenance history you remember (mileage, missed services, when you noticed it) and, when you have them, sensor readings. It answers three questions:

1. **What failed?**
2. **What was the lead-up?** Breakdowns are rarely a single event. Something has been going wrong for a while (a hardened gasket, a skipped service, repeated overheating) before a part finally gives up.
3. **What should have been done, and when?** The prevention step that would have broken the chain, and how much useful life is left.

SIRE builds several competing hypotheses, scores each one against evidence (what the photo shows, what you told it, cited knowledge retrieved from a real knowledge base, and RUL predictions from models trained on NASA C-MAPSS and N-CMAPSS) and returns the most plausible explanation with its confidence and sources.

Everything is open-source and runs locally: Qwen models for language and vision, our own RUL models, a local vector database. No hard-coded answers and no placeholder data anywhere.

## Scope note
C-MAPSS and N-CMAPSS are NASA turbofan sensor datasets, so the RUL models only apply when a sensor time series exists (turbofan-type or other instrumented machinery). A phone photo of a car has no sensor stream: photo-only cases go through perception (Phase E), retrieval (Phase C) and the hypothesis engine (Phase D). The engine treats RUL as one evidence source among several.

## Phases
| Phase | Folder | What it delivers | Depends on |
|---|---|---|---|
| A | `Phase_A_RUL_Training/` | Train and compare eight RUL models on C-MAPSS and N-CMAPSS, one at a time, starting from a LightGBM baseline. | datasets only |
| B | `Phase_B_LLM_Integration/` | Local Qwen LLM plus the RUL models as tools: data in, the LLM routes it, the model predicts, the LLM explains using only the model's numbers. | A |
| C | `Phase_C_Knowledge_RAG/` | Real documents, hybrid retrieval and cited cause-chain cards: the evidence chamber. | none (can run alongside B) |
| D | `Phase_D_Hypothesis_Engine/` | The separate brain: competing hypotheses, expected evidence, matching, scoring, follow-up questions and prevention planning. | A, B, C |
| E | `Phase_E_Vision/` | Qwen vision-language perception: photos become structured, calibrated evidence. | C, D (schemas) |
| F | `Phase_F_Frontend_Voice/` | UI imported from the Figma design, plus voice in and out. Skeleton only until Phases A-E are accepted. | API contract (implemented in G) |
| G | `Phase_G_Final_Integration/` | Gateway, model manager, end-to-end tests, full evaluation, packaging and demo. | A-F |

Work in the order A, B, C, D, E, F, G. Phase C does not depend on A and may run alongside B. Do not start a phase before the acceptance checklist of the previous one is ticked, unless the table says the phase is independent.

## Final architecture
```text
 photo(s) + text history + optional sensor file
              |
     +--------v---------+
     | Perception  (E)  |  Qwen vision-language model -> structured evidence
     +--------+---------+
              |
     +--------v-------------------------------------------------+
     | Hypothesis Engine (D) - the separate brain                |
     |  generate -> expect -> match -> score -> ask / finalize   |
     +---+------------------+-------------------+---------------+
         |                  |                   |
   +-----v------+   +-------v--------+   +------v-----------+
   | RAG (C)    |   | RUL tools (A,B)|   | LLM runtime (B)  |
   | knowledge  |   | C-MAPSS and    |   | Qwen3 orchestra- |
   | + citations|   | N-CMAPSS models|   | tion, tool calls |
   +------------+   +----------------+   +------------------+
              |
   root cause, lead-up chain, prevention, maintenance plan,
   RUL, confidence, sources
   UI + voice (F)      gateway, evaluation, packaging (G)
```

## How to drive it (VS Code + Codex)
1. Unzip, then open the `SIRE/` folder in VS Code. Codex reads `AGENTS.md` automatically.
2. Put the datasets in `Phase_A_RUL_Training/CMAPSS/data/` and `Phase_A_RUL_Training/NCMAPSS/data/`.
3. Open `Phase_A_RUL_Training/README.md`, paste the prompt from section 4 into Codex, then drive it with short commands (`setup cmapss`, `build common cmapss`, `train 01_lightgbm on FD001`, ...).
4. Every phase folder has its own `README.md` containing the prompt for that phase, the order of work, the contracts it must satisfy and an acceptance checklist.
5. `STATUS.md` is the single place that shows where the project stands. Codex updates it after every step.

## Ground rules (every phase)
- Real, working code only: no placeholders, no stubs, no mocked results, no invented data or numbers.
- Open-source models and libraries only, with their licences checked.
- Results come from code that actually ran. Failures are reported, not hidden.
- No data leakage: split by unit, vehicle or session; fit on training data only; never tune on test data.
- One phase at a time, one step at a time, each step ending with a report.

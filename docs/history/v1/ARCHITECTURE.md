# Local architecture

Browser React UI -> same-origin FastAPI -> validated services -> isolated native CPU predictor process.

The app serves the built frontend and `/api` from one loopback port. Development Vite proxies `/api` to that port. `engine/telemetry.py` reads official sensor histories and in-memory validated uploads. `engine/model_hub.py` resolves only manifest IDs, enforces dataset/task matching, limits inference concurrency and times out workers. `engine/worker.py` hash-checks preserved dependencies and calls unchanged legacy loaders. All original preprocessing/window/padding/target policies remain effective. No data fitting occurs.

`model_store/manifest.json` is the new app's canonical reference catalog; the historical Phase A registry is immutable input provenance. `verification.json` is current smoke evidence, separate from old research metrics. Models are CPU loaded on demand and released with each worker. Startup includes one actual FD001 inference before declaring `ml_ready`.

Investigation deterministically calls at most one RUL tool, one lexical retrieval and one local structured-generation call. The language model cannot execute Python, shell, files or arbitrary tools. Its hypotheses cite supplied evidence IDs and remain labeled unverified. Numeric facts come from the separate ML evidence payload. Notes and documents enter as untrusted user data.

Vision decodes bounded JPEG/PNG/WebP, discards metadata and sends a resized image only to loopback Ollama. Photos remain separate from simulated NASA assets. No hosted adapter is enabled. Local model absence leaves ML and document search available.

This edition is a single-user local demo, without authentication or durable case persistence. Do not expose it on a public interface without adding appropriate access controls, per-client limits and storage policy. Uploads are memory-only, bounded in count/size, expire after 30 minutes and are cleared at shutdown.

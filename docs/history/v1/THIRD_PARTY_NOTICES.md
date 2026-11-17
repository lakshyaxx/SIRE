# New application dependencies and example sources

The application uses permissively licensed FastAPI (MIT), Starlette (BSD), Pydantic (MIT), Uvicorn (BSD), HTTPX (BSD), python-multipart (Apache-2.0), Pillow (HPND), React (MIT), Vite (MIT), TypeScript (Apache-2.0), Tailwind CSS (MIT), Recharts (MIT), Ruff (MIT/Apache-2.0), and Black (MIT). Exact installed versions and transitives are pinned in requirements-app.lock.txt and frontend/package-lock.json. The original research dependencies remain documented separately under Phase A and requirements-runtime.lock.txt.

Ollama is MIT licensed. Its installed portable CPU runtime includes its upstream license notices under `lib/ollama/`. Qwen3 4B and Qwen3-VL 2B are listed under Apache-2.0 by the official Ollama registry. No new GPL, AGPL or non-commercial model/library was introduced for this build. The CPU runtime deliberately omits GPU extras.

The optional bearing photograph is CC0; author, source, license and byte hashes are in samples/images/PROVENANCE.md. It is not a damaged-component label or a NASA engine image. NASA C-MAPSS source data remains in the original ignored research data directory and is labeled simulation throughout the application.

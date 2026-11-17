# Dependencies and demo provenance

The app uses permissive FastAPI (MIT), Starlette (BSD), Pydantic (MIT), Uvicorn (BSD), HTTPX (BSD), python-multipart (Apache-2.0), Pillow (HPND), pypdf (BSD), PyYAML (MIT), React/React Markdown/Remark GFM (MIT), Vite (MIT), TypeScript (Apache-2.0), Tailwind (MIT), Recharts (MIT), Ruff (MIT/Apache-2.0), Black (MIT) and pytest (MIT). Versions/transitives are pinned in requirements-app.lock.txt and web/package-lock.json. The complete existing native runtime is requirements-runtime.lock.txt. No PyMuPDF or Ultralytics is used.

Ollama is MIT and retains upstream notices in its installed portable runtime. Qwen3 4B/Qwen3-VL 2B are Apache-2.0 per their checked official registry metadata. Runtime release/hash/signature: OLLAMA_RUNTIME_MANIFEST.json. Settings discovers actual installed model digests. No hosted or proprietary inference API is used. No new GPL/AGPL/non-commercial dependency was introduced.

Demo bearing media is CC0; original author/source/license/hash: data/demo/PROVENANCE.md. It is not a damaged-part label or NASA engine image. C-MAPSS is simulated research turbofan data, retained in the private ML bundle. The knowledge text is a project model card, not a third-party maintenance manual.

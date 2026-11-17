# Local deployment

Use the root README startup commands. Built UI and API share `http://127.0.0.1:8000`; API docs at `/docs`. The launcher defaults to loopback. Vite is optional for development.

The app requires the original Phase A artifact tree and NASA source histories. A fresh clone without ignored weights/data cannot reproduce inference; restore authorized local artifacts from the private checksummed snapshot. Do not commit them or put them in public frontend assets.

Ollama is optional. Once installed and explicitly approved small models are present, configure names through `config/app.yaml` or OS environment. The adapter calls `/api/tags` for installed models and `/api/chat` for schema-constrained generation, with zero keep-alive to release the model afterward. The user approved a native installation and both model downloads. A CPU-only portable Ollama 0.40.16 runtime is installed at the current Windows account?s `AppData/Local/Programs/SIRE-Ollama`. Components were extracted byte-for-byte from the official release ZIP and checked against its entry CRCs. Windows Authenticode reports Valid for the executable, signed by Ollama Inc. GPU extras were omitted to avoid the stalled large installer. Model pulls and inference verification are recorded in BUILD_STATUS.md. The launcher discovers this runtime automatically; `SIRE_OLLAMA_EXE` can override its path.

Public deployment is not performed. Hosting only the frontend cannot reach a visitor's laptop Ollama. A public edition needs a separately provisioned authenticated backend with artifact storage, sufficient CPU/RAM, HTTPS, approved upload policy and a reachable language-model runtime. LAN/phone testing also needs a deliberately configured listener and firewall; camera capture may require a secure context. Do not open a tunnel or firewall automatically.

Implementation references checked: [FastAPI uploads](https://fastapi.tiangolo.com/tutorial/request-files/), [Vite guide](https://vite.dev/guide/), [Ollama chat](https://docs.ollama.com/api/chat), [Ollama model list](https://docs.ollama.com/api/tags).


The installed portable runtime?s original-file hashes and official release URL are recorded in OLLAMA_RUNTIME_MANIFEST.json. On another machine, install that official Ollama version normally (or use its portable release), start its local service, and run `ollama pull qwen3:4b` and `ollama pull qwen3-vl:2b-instruct`. The app does not download weights on startup. Model digests are recorded after successful pulls. The CPU build trades performance for a much smaller runtime download; GPU libraries and GPU inference are not installed or benchmarked.

The explicit `qwen3-vl:2b-instruct` tag is used for short structured image observations. The default `qwen3-vl:2b` resolved to the thinking variant during this build and exhausted response budgets in full API requests. Both are preserved locally; no original model was deleted.

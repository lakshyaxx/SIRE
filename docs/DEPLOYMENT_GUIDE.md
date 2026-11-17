# V3.2 current local operation

The verified app now serves on loopback 8000 with the existing user state. Start scripts/dev.ps1 or python scripts/dev.py; never launch publicly by default. See V3_2_RUNBOOK.md and V3_2_HANDOFF_REPORT.md for current checks, actual process IDs and recovery. Optional local ASR/TTS/video is installed in ignored isolated directories; setup and licence/provenance details are in MEDIA_PROVENANCE.md. Startup never downloads dependencies/weights. Browser/hardware and clean/non-Windows installation acceptance remain unverified. scripts/export_runtime.py defaults to a separate V3.2 ZIP; original V2/V3 ZIPs are preserved. Root .venv still depends on the protected external third-party environment.

The original V3 deployment checkpoint below is historical; its unavailable-media and default-export statements are superseded above.

---

# V3 local launch and deployment boundary

From the repository, run `.\scripts\dev.ps1`. Open http://127.0.0.1:8000 and /engineer; API docs at /docs. The Python equivalent is `.venv/Scripts/python.exe scripts/dev.py`. The launcher seeds a missing synthetic-only scenario directory idempotently before serving and starts an already installed local Ollama when needed. It never installs/downloads models, opens a public listener or controls equipment.

Current root venv still uses a .pth pointing to C:/Users/laksh/SIRE_SAFETY_BACKUPS/v2_retired_20261117/environment/Lib/site-packages. Keep that environment. No clean replacement/fresh network install is claimed. Source/artifacts use relative roots; current Windows CPU execution was tested. Other platforms need suitable dependency wheels; the captured Windows CUDA lock is not a tested cross-platform lock.

Config: config/app.yaml for local provider/upload/timeouts and config/simulation.yaml for reproducible toy settings. OS overrides: SIRE_TEXT_MODEL, SIRE_VISION_MODEL, OLLAMA_BASE_URL (loopback only), SIRE_STATE_DIR and SIRE_OLLAMA_EXE. SIRE_WEB_BUILD accepts dist or dist-v3 for staged UI QA. App does not load .env automatically. Installed verified instruct tags are qwen3:4b-instruct and qwen3-vl:2b-instruct; no embeddings/ASR/TTS/video runtime is configured.

Protected pre-V3 source/SQLite backup: .runtime/v3_backups. Original external snapshots remain intact. Back up the entire state directory while stopped, including SQLite and private imports/attachments. V3 schema migration is additive/idempotent; old V2 conversations are not copied into a new app or reset. Upload retention is local and explicit; V3 audit originals/excerpts remain until reviewed maintenance outside this task.

Verification: scripts/verify_v3.ps1 (or python scripts/verify_v3.py), optionally --full-model-audit for a slow fresh 168-route run. scripts/demo_smoke.py --base http://127.0.0.1:8000 calls real providers and tools. scripts/evaluate_scenarios.py evaluates only hidden synthetic truth offline. scripts/export_runtime.py creates a private V3 ZIP and per-file CRC/SHA manifest, preserving the old V2 ZIP. It excludes user state/imports, environments, Node modules, Ollama weights, truth databases and research archive; generator code remains so a fresh install can seed its own clearly labeled scenarios. It is not a standalone offline installer.

No public deployment occurred. This single-user loopback app has no multi-user authentication. Public hosting requires separate approval and an authenticated resource-provisioned backend, HTTPS/private uploads and artifact storage; static hosting cannot call a visitor's laptop Ollama. Browser/mobile/camera/microphone interactions remain unverified because browser tooling was blocked. No security control was bypassed.

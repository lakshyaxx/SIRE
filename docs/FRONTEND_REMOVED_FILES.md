# Frontend consolidation record

The canonical frontend is `web/`. This cleanup is reversible and local; no research, model, production database or frozen stress result is removed.

Before integration, source archives and per-file hashes were saved in the ignored checkpoint identified by `.runtime/frontend_integration_current.txt`. The original delivered export `sire front/` was moved intact into that checkpoint, including its private browser profile and dependencies. Those private files must never be committed or published. The original source ZIP remains independently recoverable.

The following unreachable presentation files were retired into the same ignored checkpoint: delivered `AttachmentComposer.tsx`, `VoiceVisualization.tsx`, `UnavailableFeature.tsx`, `pages/Overview.tsx`; old `features/settings/Settings.tsx`, `features/investigations/Cases.tsx`, and old `styles/app.css`, `styles/tokens.css`. Import searches found no consumers except the hidden Overview route, which now redirects to actual case history. Functional replacements are the retained Chat/VoiceSession controllers, connected status/settings, real paginated case history and delivered theme plus integration CSS. Original knowledge ingestion remains reachable through a document-workspace route.

Exact movement receipts are in `.runtime/frontend_integration_20261119_005543/retirement.json`. The final audit rehashed the delivered source in its new location and found zero differences; both original ZIPs passed SHA-256 and CRC verification. No permanent deletion, Git reset, commit or publication is performed.

# Voice integration and acceptance scope

`/live/:id?` uses the same retained chat controller and conversation ID as text. Starting the explicit live control enables automatic reply audio. PCM microphone frames reach the existing local WebSocket/Silero session; final English Whisper transcripts retain source attachment IDs and automatically submit an ordinary chat turn. Backend route selection depends on content and actual evidence, not simply the existence of an audio provenance record. Manual recording/review remains available.

ReadReply and InlineSpeech retain actual local Kokoro synthesis and bounded playback, with installed local browser voice fallback only when explicitly selected. Selected microphone, speaker (where setSinkId is supported) and volume preferences are wired through. Stop and navigation close owned capture/playback. Playback gating suppresses microphone feedback and resets accumulated frames; VAD candidate events cannot cancel an answer. Deliberate `Interrupt and speak` invokes scoped cancellation. Duplicate final transcript IDs and stale sockets are guarded.

## Measured evidence

All seven fresh offline-process checks passed, including actual local Kokoro synthesis (10.135185s) and Whisper transcription (2.255950s). This blocks external Python sockets/DNS in that process/workers, while permitting local Ollama; it is not an OS air-gap guarantee.

Actual network TTS cases took 8.776786s, 5.721433s, 11.059158s and 27.522490s for progressively different actual text inputs. Raw text/audio/tool results are private in `network/results.json`. Cached ASR reads around 0.1s are not fresh recognition latency. Fresh media extraction happened at upload, and the independent offline recognition above is a fresh measured operation. CPU speech startup remains a noticeable limitation.

Frontend VoiceGate, PCM, speech-queue/cancel and actual-controller tests passed within the 24-test suite. Browser Live Conversation rendered real start/manual-record/auto-reply controls at phone/tablet widths. No physical capture permission was granted in automated QA. Genuine microphone transcription, audible autoplay, chosen hardware speaker, acoustic noise and deliberate spoken interruption are **unverified**, so real-time/full-duplex voice acceptance is not declared.

Next physical acceptance: start live capture with user permission; say Hello; follow text↔voice in the same chat; verify automatic audible response; deliberately interrupt via the exposed control; confirm background noise and assistant playback do not create turns; stop and verify mic indicator closes. Preserve logs and observed timestamps rather than estimating audio onset.

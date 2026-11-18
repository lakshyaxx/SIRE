# Phase 3 GPU verification

Both configured Qwen families actually ran on the NVIDIA RTX 4050 Laptop GPU. This phase retained the already repaired same-version Ollama CUDA runtime; no installation or new models were needed.

Actual text `ollama ps`:

```text
NAME                 ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL                   
qwen3:4b-instruct    0edcdef34593    3.2 GB    100% GPU     4096       llamacpp    About a minute from now
```

Actual vision observation during the final fresh investigation:

```text
NAME                    ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL                   
qwen3-vl:2b-instruct    afc393e3572c    2.0 GB    100% GPU     4096       llamacpp    About a minute from now
```

Actual `nvidia-smi` point sample (name, driver, used VRAM, total VRAM, utilization):

```text
NVIDIA GeForce RTX 4050 Laptop GPU, 621.01, 3794 MiB, 6141 MiB, 5 %
```

This utilization is a point sample, not an average or peak. Text residency reports Q4_K_M and 3180247121 VRAM bytes. Vision has an actual positive VRAM allocation in the final-network receipt. CLI 100% GPU describes offloading, not 100% compute utilization. Per-layer text/vision/CLIP logs in earlier runtime diagnosis are historical; this release's direct proof is fresh CLI plus residency/inference, not a new per-layer audit.

Supplementary root Torch: 2.8.0+cu128, compiled CUDA 12.8, CUDA available True. Torch availability alone would not prove Ollama GPU use. All 51 installed runtime files (33 original plus 18 previous CUDA additions) retain verified hashes.

Keep one loaded Ollama model and one parallel request; keepalive 120s. Existing OS-scoped heavy-operation lease serializes cooperating workers. No aggressive concurrent text/VLM loads, no new quantization, no forced GPU-memory reservation, no extra speculative GPU preload. CPU Kokoro, Whisper and MiniLM remain CPU providers rather than competing for laptop VRAM. Genuine native NASA models keep their original inference policy.

Cancellation was observed during actual positive-VRAM inference and terminated in 0.308s. Missing-tag failure is explicit. Separate KV allocation, peak whole-system RAM/VRAM, deliberate OOM recovery and sustained thermal behavior were not measured. No estimate is substituted. [Actual receipts](PHASE3_RESULTS.json).

import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const require = createRequire(new URL("../package.json", import.meta.url));
const { buildSync } = require("esbuild");
function source(path) {
  const output = buildSync({
    entryPoints: [fileURLToPath(new URL(path, import.meta.url))],
    bundle: true,
    platform: "node",
    format: "cjs",
    write: false,
    logLevel: "silent",
    jsx: "automatic",
    external: [
      "react",
      "react-dom",
      "react-dom/server",
      "react/jsx-runtime",
      "react-router",
    ],
  }).outputFiles[0].text;
  const module = { exports: {} };
  new Function("require", "module", "exports", output)(
    require,
    module,
    module.exports,
  );
  return module.exports;
}
const adapter = source("../src/services/api.ts");
const transport = source("../src/lib/api.ts");
const validation = source("../src/utils/validation.ts");

test("failed investigations preserve submitted files, requested identity and sanitized failed stage", () => {
  const detail = adapter.presentInvestigation({
    id: "unit-failed-job",
    kind: "job",
    conversation_id: "unit-cid",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:01Z",
    status: "error",
    question: "Investigate UNIT-017",
    evidence_count: 0,
    requested_asset_id: "UNIT-017",
    asset_identity_source: "user_question",
    attachments: [
      { id: "unit-csv", name: "unit.csv", kind: "csv" },
      { id: "unit-pdf", name: "unit.pdf", kind: "document" },
      { id: "unit-image", name: "unit.png", kind: "image" },
    ],
    failure: {
      code: "unit_tool_failed",
      message: "Explicit unit sanitized tool failure",
      stage: "measurements.profile",
    },
    job: { events: [] },
  });
  assert.equal(detail.assetId, "UNIT-017");
  assert.equal(detail.assetIdentitySource, "user_question");
  assert.equal(detail.attachments.length, 3);
  assert.equal(detail.error.message, "Explicit unit sanitized tool failure");
  assert.equal(detail.stage, "error · measurements.profile");
  assert.equal(detail.hypotheses.length, 0);
  assert.equal(detail.recommendations.length, 0);
  assert.equal(
    detail.summary,
    undefined,
    "A failure message is not an investigation finding or speech summary",
  );
});

test("three-file intake persists every actual receipt on the same job request", async (t) => {
  const oldFetch = globalThis.fetch,
    oldWindow = globalThis.window;
  t.after(() => {
    globalThis.fetch = oldFetch;
    globalThis.window = oldWindow;
  });
  globalThis.window = new EventTarget();
  const uploaded = [];
  let submitted;
  globalThis.fetch = async (url, options) => {
    await Promise.resolve();
    if (url.endsWith("/conversations"))
      return Response.json({ id: "unit-three-files" });
    if (url.endsWith("/attachments")) {
      assert.equal(options.body.get("conversation_id"), "unit-three-files");
      const id = "unit-file-" + uploaded.length;
      uploaded.push(options.body.get("file").name);
      return Response.json({ id, metadata: {}, ingestion_status: "ready" });
    }
    submitted = JSON.parse(options.body);
    return Response.json({
      id: "unit-job",
      status: "queued",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
  };
  const form = new FormData();
  form.set("question", "Investigate UNIT-017 without calculating RUL");
  for (const name of ["unit.csv", "unit.pdf", "unit.png"])
    form.append(
      "evidence",
      new File(["Explicit unit transport-only bytes"], name),
    );
  await adapter.api.createInvestigation(form);
  assert.deepEqual(uploaded, ["unit.csv", "unit.pdf", "unit.png"]);
  assert.deepEqual(submitted.attachment_ids, [
    "unit-file-0",
    "unit-file-1",
    "unit-file-2",
  ]);
  assert.equal(submitted.conversation_id, "unit-three-files");
  assert.equal(submitted.mode, "investigate");
});
const fakeReport = {
  id: "test-only-case",
  case: {
    question: "Explicit test-only investigation",
    conversation_id: "test-only-conversation",
    evidence: [
      {
        id: "test-only-source",
        modality: "csv",
        kind: "measurement",
        source_id: "test-only-file",
        observation: "Explicit test-only observed source value",
        reliability: "high",
        limitations: [],
      },
    ],
  },
  hypotheses: [
    {
      id: "Z-test",
      mechanism: "Explicit test-only first candidate.",
      assumptions: ["Test-only unknown"],
      supporting_evidence_ids: ["test-only-source"],
      contradicting_evidence_ids: [],
      missing_tests: ["Test-only inspection"],
      status: "tentative",
      evidence_support: "limited",
    },
    {
      id: "A-test",
      mechanism: "Explicit test-only rejected candidate.",
      assumptions: [],
      supporting_evidence_ids: [],
      contradicting_evidence_ids: ["test-only-source"],
      missing_tests: [],
      status: "rejected",
      evidence_support: "low",
    },
  ],
  unresolved: ["Test-only unanswered question"],
  limitations: ["Explicit test-only limitation"],
  rounds: 1,
  stop_reason: "test_only_stop",
};

test("canonical citations resolve their actual evidence locator beyond the source-library page", () => {
  assert.equal(
    adapter.referenceAttachmentId({
      source: { id: "test-only-source" },
      evidence: { pointer: { attachment_id: "test-only-original" } },
    }),
    "test-only-original",
  );
  assert.equal(
    adapter.referenceAttachmentId({
      source: { pointer: { attachment_id: "incorrect-location" } },
      evidence: { pointer: {} },
    }),
    undefined,
  );
});

test("actual presentation adapter retains ordering, contradictions, source identity and uncertainty", () => {
  const detail = adapter.presentInvestigation({
    id: "test-only-case",
    kind: "case",
    conversation_id: "test-only-conversation",
    created_at: "2026-11-18T00:00:00Z",
    updated_at: "2026-11-18T00:00:00Z",
    status: "complete",
    question: fakeReport.case.question,
    evidence_count: 1,
    report: fakeReport,
  });
  assert.deepEqual(
    detail.hypotheses.map((h) => h.id),
    ["Z-test", "A-test"],
  );
  assert.equal(detail.hypotheses[1].classification, "unsupported");
  assert.equal(
    detail.hypotheses[1].contradictoryEvidence[0].evidenceId,
    "test-only-source",
  );
  assert.equal(detail.uncertainty, "Explicit test-only limitation");
  assert.equal(detail.conversationId, "test-only-conversation");
});

test("job activity does not invent event timestamps from the record update time", () => {
  const value = adapter.presentInvestigation({
    id: "test-only-job",
    kind: "job",
    conversation_id: "test-only-conversation",
    created_at: "2026-11-18T00:00:00Z",
    updated_at: "2026-11-18T01:00:00Z",
    status: "running",
    question: "Explicit test-only question",
    evidence_count: 0,
    job: {
      id: "test-only-job",
      events: [{ type: "tool", tool: "test-only-tool", status: "complete" }],
    },
  });
  assert.equal(value.activity[0].at, undefined);
  assert.equal(value.updatedAt, "2026-11-18T01:00:00Z");
});

test("terminal job status overrides stale running events and source statistics stay human-readable", () => {
  const value = adapter.presentInvestigation({
    id: "test-only-job",
    kind: "job",
    conversation_id: "test-only-conversation",
    created_at: "2026-11-18T00:00:00Z",
    updated_at: "2026-11-18T01:00:00Z",
    status: "complete",
    question: "Explicit test-only question",
    evidence_count: 0,
    job: {
      events: [{ type: "tool", tool: "test-only-engine", status: "running" }],
    },
  });
  assert.equal(value.stage, "complete");
  const source = JSON.stringify({
    asset_id: "test-only-asset",
    channel: "test_only_channel",
    unit: "test-only-unit",
    baseline_mean: 2,
    recent_mean: 3,
    delta: 1,
    count: 4,
  });
  const text = adapter.observationText(source, "measurement");
  assert.ok(text.includes("test-only-asset"));
  assert.ok(text.includes("baseline 2 test-only-unit"));
  assert.ok(text.includes("recent 3 test-only-unit"));
  assert.ok(!text.includes("{"));
  assert.equal(
    adapter.observationText(source, "user_claim"),
    source,
    "User-supplied JSON is not promoted to computed measurement prose",
  );
});

test("capability facade uses actual SIRE endpoints and preserves unavailable providers", async (t) => {
  const previous = globalThis.fetch;
  t.after(() => (globalThis.fetch = previous));
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return Response.json(
      url.endsWith("/health")
        ? {
            application_version: "test-only",
            text_ready: false,
            vision_ready: false,
            ollama_ready: false,
          }
        : url.endsWith("/voice/capabilities")
          ? { asr_ready: false, tts_ready: false }
          : {
              checked_at: "2026-11-18T00:00:00Z",
              max_upload_bytes: 1234,
              upload_extensions: [".csv", ".pdf"],
            },
    );
  };
  const result = await adapter.api.capabilities();
  assert.equal(result.qwen.state, "unavailable");
  assert.equal(result.kokoro.state, "unavailable");
  assert.equal(result.uploads.maxBytes, 1234);
  assert.deepEqual(calls.sort(), [
    "/api/v1/frontend/config",
    "/api/v1/health",
    "/api/v1/voice/capabilities",
  ]);
});

test("actual intake awaits real upload receipts and sends their IDs with the same conversation", async (t) => {
  const previous = globalThis.fetch,
    window = globalThis.window;
  t.after(() => {
    globalThis.fetch = previous;
    globalThis.window = window;
  });
  globalThis.window = new EventTarget();
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    if (url.endsWith("/conversations"))
      return Response.json({ id: "test-only-conversation" });
    if (url.endsWith("/attachments"))
      return Response.json({
        id: "test-only-attachment",
        metadata: {},
        ingestion_status: "ready",
      });
    return Response.json({
      id: "test-only-job",
      status: "queued",
      created_at: "2026-11-18T00:00:00Z",
      updated_at: "2026-11-18T00:00:00Z",
    });
  };
  const form = new FormData();
  form.set("question", "Explicit test-only question");
  form.set(
    "evidence",
    new File(["Explicit test-only file bytes"], "test-only.txt", {
      type: "text/plain",
    }),
  );
  const result = await adapter.api.createInvestigation(form);
  assert.equal(result.id, "test-only-job");
  assert.equal(
    calls[1][1].body.get("conversation_id"),
    "test-only-conversation",
  );
  const job = JSON.parse(calls[2][1].body);
  assert.deepEqual(job.attachment_ids, ["test-only-attachment"]);
  assert.equal(job.conversation_id, "test-only-conversation");
  assert.equal(job.mode, "investigate");
});

test("failed extraction never creates an investigation or a fabricated upload success", async (t) => {
  const previous = globalThis.fetch,
    previousWindow = globalThis.window;
  t.after(() => {
    globalThis.fetch = previous;
    globalThis.window = previousWindow;
  });
  globalThis.window = new EventTarget();
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return Response.json(
      url.endsWith("/conversations")
        ? { id: "test-only-conversation" }
        : {
            id: "test-only-attachment",
            ingestion_status: "failed",
            metadata: {
              media_error: { message: "Explicit test-only extraction failure" },
            },
          },
    );
  };
  const form = new FormData();
  form.set("question", "Explicit test-only question");
  form.set("evidence", new File(["test-only"], "bad.txt"));
  await assert.rejects(
    () => adapter.api.createInvestigation(form),
    /extraction failure/,
  );
  assert.equal(calls.length, 2);
});

test("published extension policy handles empty MIME and rejects unsupported suffixes and too many files", () => {
  assert.equal(
    validation.acceptsFile({ name: "test-only.CSV", type: "" }, [".csv"]),
    true,
  );
  assert.equal(
    validation.acceptsFile(
      { name: "test-only.exe", type: "application/octet-stream" },
      [".pdf", ".csv"],
    ),
    false,
  );
  const result = validation.validateInvestigation(
    "Explicit test-only question",
    Array.from(
      { length: 7 },
      () => new File(["a"], "test-only.csv", { type: "text/csv" }),
    ),
    { state: "available", acceptedTypes: [".csv"], maxBytes: 20 },
  );
  assert.equal(result.valid, false);
  assert.ok(result.fileErrors.some((text) => text.includes("six")));
});

test("actual SSE parser handles split CRLF/UTF8 and requires a real terminal event", async (t) => {
  const previous = globalThis.fetch;
  t.after(() => (globalThis.fetch = previous));
  const data = new TextEncoder().encode(
    'data: {"type":"delta","text":"Test-only α"}\r\n\r\ndata: {"type":"done","status":"complete"}\r\n\r\n',
  );
  globalThis.fetch = async () =>
    new Response(
      new ReadableStream({
        start(controller) {
          for (let index = 0; index < data.length; index += 3)
            controller.enqueue(data.slice(index, index + 3));
          controller.close();
        },
      }),
    );
  const events = [];
  await transport.streamMessage({}, new AbortController().signal, (value) =>
    events.push(value),
  );
  assert.equal(events[0].text, "Test-only α");
  assert.equal(events.at(-1).status, "complete");
  globalThis.fetch = async () =>
    new Response('data: {"type":"delta","text":"Test-only incomplete"}\n\n');
  await assert.rejects(
    () => transport.streamMessage({}, new AbortController().signal, () => {}),
    /before completion/,
  );
});

test("delivered findings render actual evidence links, contradictions and bounded uncertainty", () => {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const { MemoryRouter } = require("react-router");
  const { Findings } = source("../src/pages/InvestigationWorkspace.tsx");
  const detail = adapter.presentInvestigation({
    id: "test-only-case",
    kind: "case",
    conversation_id: "test-only-conversation",
    created_at: "2026-11-18T00:00:00Z",
    updated_at: "2026-11-18T00:00:00Z",
    status: "complete",
    question: fakeReport.case.question,
    evidence_count: 1,
    report: fakeReport,
  });
  const html = renderToStaticMarkup(
    React.createElement(
      MemoryRouter,
      null,
      React.createElement(Findings, { detail }),
    ),
  );
  assert.ok(html.includes("Explicit test-only limitation"));
  assert.ok(html.includes("Contradictory Evidence"));
  assert.ok(html.includes("evidence=test-only-source"));
  assert.ok(!html.includes("90%"));
});

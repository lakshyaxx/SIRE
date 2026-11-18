import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { actualSource } from "./source.mjs";
const require = createRequire(new URL("../package.json", import.meta.url));

test("first attachment survives New conversation URL transition and is sent with the actual receipt ID", async (t) => {
  const { JSDOM } = require("jsdom");
  const React = require("react");
  const { act } = React;
  const { createRoot } = require("react-dom/client");
  const dom = new JSDOM('<div id="root"></div>', {
    url: "http://127.0.0.1:8001/?new=test-only-epoch",
  });
  const saved = new Map();
  for (const key of [
    "window",
    "document",
    "navigator",
    "location",
    "localStorage",
    "sessionStorage",
    "Event",
    "CustomEvent",
    "HTMLElement",
    "IS_REACT_ACT_ENVIRONMENT",
    "fetch",
  ])
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
  for (const key of [
    "window",
    "document",
    "navigator",
    "location",
    "localStorage",
    "sessionStorage",
    "Event",
    "CustomEvent",
    "HTMLElement",
  ])
    Object.defineProperty(globalThis, key, {
      value: key === "window" ? dom.window : dom.window[key],
      configurable: true,
      writable: true,
    });
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  dom.window.HTMLElement.prototype.scrollIntoView = function () {};
  let root;
  let finishUpload;
  let posted;
  let uploadBody;
  let failSubmission = false;
  let posts = 0;
  t.after(async () => {
    if (root) await act(async () => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  });
  const receipt = {
    id: "test-only-file-id",
    conversation_id: "test-only-created-conversation",
    name: "test-only-upload.txt",
    kind: "document",
    mime: "text/plain",
    sha256: "a".repeat(64),
    metadata: {},
    ingestion_status: "ready",
  };
  globalThis.fetch = async (url, options = {}) => {
    if (url.endsWith("/providers"))
      return Response.json({
        models: [{ name: "test-only-local-model" }],
        configured_text: "test-only-local-model",
        health: {},
      });
    if (url.endsWith("/conversations") && options.method === "POST")
      return Response.json({ id: "test-only-created-conversation" });
    if (url.endsWith("/attachments")) {
      uploadBody = options.body;
      return new Promise((resolve, reject) => {
        finishUpload = () => resolve(Response.json(receipt));
        options.signal.addEventListener(
          "abort",
          () =>
            reject(
              new DOMException(
                "Explicit test-only cancelled transport",
                "AbortError",
              ),
            ),
          { once: true },
        );
      });
    }
    if (url.includes("/investigation-jobs?")) return Response.json([]);
    if (url.endsWith("/chat/message")) {
      posts++;
      posted = JSON.parse(options.body);
      if (failSubmission)
        return Response.json(
          { error: { message: "Explicit test-only submission failure" } },
          { status: 503 },
        );
      return new Response(
        'data: {"type":"started","user_message_id":"test-only-user"}\n\ndata: {"type":"done","status":"complete","metadata":{"tools":[],"evidence":[]}}\n\n',
      );
    }
    if (url.includes("/conversations/test-only-created-conversation"))
      return Response.json({
        id: "test-only-created-conversation",
        messages: [],
        attachments: posted ? [receipt] : [],
      });
    throw new Error(
      "Unexpected actual-component request in explicit unit fixture: " + url,
    );
  };
  const { Assistant, PreferencesProvider } = actualSource(
    "./fixtures/assistant.ts",
  );
  const {
    createMemoryRouter,
    Outlet,
    RouterProvider,
  } = require("react-router");
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: React.createElement(
          PreferencesProvider,
          null,
          React.createElement(Outlet),
        ),
        children: [
          { index: true, element: React.createElement(Assistant) },
          { path: "chat/:id", element: React.createElement(Assistant) },
        ],
      },
    ],
    { initialEntries: ["/?new=test-only-epoch"] },
  );
  await act(async () => {
    root = createRoot(dom.window.document.getElementById("root"));
    root.render(React.createElement(RouterProvider, { router }));
  });
  const input = dom.window.document.querySelector(
    'input[type="file"][multiple]',
  );
  assert.ok(input);
  Object.defineProperty(input, "files", {
    configurable: true,
    value: [
      new File(["Explicit test-only upload bytes"], "test-only-upload.txt", {
        type: "text/plain",
      }),
    ],
  });
  await act(async () => {
    input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    await new Promise((resolve) => setImmediate(resolve));
  });
  assert.equal(
    router.state.location.pathname,
    "/chat/test-only-created-conversation",
  );
  assert.ok(finishUpload);
  assert.ok(
    dom.window.document.body.textContent.includes("test-only-upload.txt"),
    "Pending upload survives navigation instead of disappearing with a remounted composer",
  );
  await act(async () => {
    finishUpload();
    await new Promise((resolve) => setImmediate(resolve));
  });
  assert.equal(
    uploadBody.get("conversation_id"),
    "test-only-created-conversation",
  );
  assert.equal(
    await uploadBody.get("file").text(),
    "Explicit test-only upload bytes",
  );
  const button = dom.window.document.querySelector(
    'button[aria-label="Send message"]',
  );
  assert.equal(
    button.disabled,
    false,
    "Confirmed pending receipt enables submission",
  );
  await act(async () => {
    button.click();
    button.click();
    await new Promise((resolve) => setImmediate(resolve));
  });
  assert.deepEqual(posted.attachment_ids, ["test-only-file-id"]);
  assert.equal(posted.conversation_id, "test-only-created-conversation");
  assert.equal(
    posts,
    1,
    "A rapid repeated click does not submit a duplicate turn",
  );
  await act(async () => {
    input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    await new Promise((resolve) => setImmediate(resolve));
  });
  await act(async () => {
    finishUpload();
    await new Promise((resolve) => setImmediate(resolve));
  });
  failSubmission = true;
  await act(async () => {
    dom.window.document
      .querySelector('button[aria-label="Send message"]')
      .click();
    await new Promise((resolve) => setImmediate(resolve));
  });
  assert.equal(
    dom.window.document.querySelector('button[aria-label="Send message"]')
      .disabled,
    false,
    "Rejected submission restores its pending receipt for retry",
  );
  assert.ok(
    dom.window.document.body.textContent.includes(
      "Explicit test-only submission failure",
    ),
  );
});

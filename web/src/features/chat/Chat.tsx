import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Paperclip, Camera, ArrowUp, Square } from "lucide-react";
import {
  api,
  streamMessage,
  type Attachment,
  type Detail,
  type Message,
  type Meta,
  type Investigation,
  type Evidence,
  type Tool,
  type InvestigationJob,
} from "../../lib/api";
import { RecordVoice, ReadReply } from "./Voice";
const Inspector = lazy(() =>
  import("../workspace/Inspector").then((module) => ({
    default: module.Inspector,
  })),
);
import type { Scope, Workspace } from "../workspace/types";
import { citationLinks } from "../../lib/citations";
import { Trace } from "../../components/Trace";
import { BackgroundInvestigation } from "./BackgroundInvestigation";
import { VoiceSession, type VoiceTurn } from "./VoiceSession";

type UploadRow = {
  key: string;
  file: File;
  status:
    | "selected"
    | "uploading"
    | "ready"
    | "failed"
    | "cancelled"
    | "attached_to_message"
    | "submitted";
  attachment?: Attachment;
  error?: string;
  elapsedMs?: number;
  mediaId?: string;
};

type Props = {
  id: string | null;
  model: string;
  predictionId: string | null;
  navigate: (path: string) => void;
  refresh: () => void;
  setBusy: (value: boolean) => void;
  welcome?: ReactNode;
  liveVoice?: boolean;
  speechEnabled?: boolean;
  audioPreferences?: {
    microphoneId: string;
    speakerId: string;
    playbackVolume: number;
  };
};
export function Chat({
  id,
  model,
  predictionId,
  navigate,
  refresh,
  setBusy: outerBusy,
  welcome,
  liveVoice = false,
  speechEnabled = true,
  audioPreferences,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [pending, setPending] = useState<Attachment[]>([]);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("chat");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [backgroundSubmitted, setBackgroundSubmitted] = useState<string | null>(
    null,
  );
  const [voiceMode, setVoiceMode] = useState(false);
  const [voiceReply, setVoiceReply] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<string | null>(predictionId);
  const [stage, setStage] = useState("");
  const [requestedSource, setRequestedSource] = useState<{
    id: string;
    nonce: number;
  } | null>(null);
  const [inspector, setInspector] = useState(false);
  const [scope, setScope] = useState<Scope | null>(null);
  const [inspected, setInspected] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const file = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const uploadLock = useRef(false);
  const removedUploads = useRef(new Set<string>());
  const uploadRequests = useRef(new Map<string, AbortController>());
  const conversation = useRef<string | null>(id);
  const creating = useRef<Promise<string> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const job = useRef("");
  const running = useRef(false);
  useEffect(() => {
    if (id !== conversation.current)
      window.dispatchEvent(new Event("sire:voice-session-stop"));
    if ((running.current || uploadLock.current) && id === conversation.current)
      return;
    if (running.current || uploadLock.current) {
      controller.current?.abort();
      uploadRequests.current.forEach((request) => request.abort());
    }
    conversation.current = id;
    creating.current = null;
    setVoiceReply(null);
    setVoiceMode(false);
    window.dispatchEvent(new Event("sire:stop-speech"));
    setUploads([]);
    setPending([]);
    setError("");
    setPrediction(predictionId);
    setMessages([]);
    setAttachments([]);
    if (id)
      api<Detail>(`/conversations/${id}`)
        .then((d) => {
          if (conversation.current !== id) return;
          setMessages(d.messages);
          setAttachments(d.attachments);
          setScope(
            [...d.messages].reverse().find((m) => m.metadata.workspace)
              ?.metadata.workspace?.context ||
              [...d.messages].reverse().find((m) => m.metadata.context)
                ?.metadata.context ||
              null,
          );
          setInspected(null);
        })
        .catch((e) => setError(e.message));
    else {
      setMessages([]);
      setAttachments([]);
      setScope(null);
      setInspected(null);
    }
  }, [id, predictionId]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages, stage]);
  useEffect(
    () => () => {
      controller.current?.abort();
      uploadRequests.current.forEach((request) => request.abort());
    },
    [],
  );
  async function ensureConversation() {
    if (conversation.current) return conversation.current;
    if (!creating.current)
      creating.current = api<{ id: string }>("/conversations", {}).then(
        (c) => c.id,
      );
    try {
      const cid = await creating.current;
      conversation.current = cid;
      navigate(`/chat/${cid}`);
      refresh();
      return cid;
    } finally {
      creating.current = null;
    }
  }
  function updateUpload(key: string, patch: Partial<UploadRow>) {
    setUploads((items) =>
      items.map((item) => (item.key === key ? { ...item, ...patch } : item)),
    );
  }
  function removeUpload(row: UploadRow) {
    removedUploads.current.add(row.key);
    uploadRequests.current.get(row.key)?.abort();
    if (row.mediaId)
      void api("/voice/cancel", { request_id: row.mediaId }).catch(() => {});
    setPending((items) =>
      items.filter((item) => item.id !== row.attachment?.id),
    );
    setUploads((items) => items.filter((item) => item.key !== row.key));
  }
  async function upload(
    files: FileList | File[],
    mediaId?: string,
    retryKey?: string,
  ) {
    const selected = Array.from(files);
    if (!selected.length) return;
    if (uploadLock.current || running.current) {
      setError("Wait for the current upload or response before adding files.");
      return;
    }
    if (selected.length + pending.length > 6) {
      setError(
        "A message can use at most six attachments. Remove one before adding more.",
      );
      return;
    }
    if (
      selected.filter((f) => f.type.startsWith("image/")).length +
        pending.filter((f) => f.kind === "image").length >
      3
    ) {
      setError("A message can use at most three images.");
      return;
    }
    setError("");
    setUploading(true);
    outerBusy(true);
    uploadLock.current = true;
    const queued = selected.map((file) => ({
      key: retryKey ?? crypto.randomUUID(),
      file,
      status: "selected" as const,
      mediaId,
    }));
    setUploads((items) => [
      ...items.filter((item) => item.key !== retryKey),
      ...queued,
    ]);
    try {
      const cid = await ensureConversation();
      for (const row of queued) {
        if (conversation.current !== cid) break;
        if (removedUploads.current.has(row.key)) continue;
        const abort = new AbortController();
        uploadRequests.current.set(row.key, abort);
        const began = performance.now();
        updateUpload(row.key, { status: "uploading" });
        try {
          const form = new FormData();
          form.append("conversation_id", cid);
          form.append("file", row.file);
          if (mediaId) form.append("media_request_id", mediaId);
          const item = await api<Attachment>(
            "/attachments",
            form,
            undefined,
            abort.signal,
          );
          if (conversation.current !== cid) break;
          if (removedUploads.current.has(row.key)) continue;
          setAttachments((items) =>
            items.some((existing) => existing.id === item.id)
              ? items
              : [...items, item],
          );
          if (item.ingestion_status === "failed" || item.metadata.media_error)
            throw new Error(
              item.metadata.media_error?.message ??
                "File was stored, but parsing failed. Retry or choose a supported file.",
            );
          updateUpload(row.key, {
            status: "ready",
            attachment: item,
            elapsedMs: performance.now() - began,
          });
          setPending((items) =>
            items.some((existing) => existing.id === item.id)
              ? items
              : [...items, item],
          );
          if (item.metadata.transcript)
            setText((previous) =>
              [previous, item.metadata.transcript!.text]
                .filter(Boolean)
                .join("\n\n"),
            );
        } catch (e) {
          const cancelled = (e as Error).name === "AbortError";
          updateUpload(row.key, {
            status: cancelled ? "cancelled" : "failed",
            error: cancelled
              ? "Cancelled in this browser. A stored file may still appear in Sources after reload."
              : (e as Error).message,
          });
        } finally {
          uploadRequests.current.delete(row.key);
        }
      }
    } catch (e) {
      setError((e as Error).message);
      for (const row of queued)
        updateUpload(row.key, {
          status: "failed",
          error: (e as Error).message,
        });
    } finally {
      uploadLock.current = false;
      setUploading(false);
      outerBusy(false);
      refresh();
    }
  }
  function updateAssistant(update: (row: Message) => Message) {
    setMessages((previous) =>
      previous.map((row) => (row.id === "live-response" ? update(row) : row)),
    );
  }
  async function send(e?: FormEvent, voice?: VoiceTurn) {
    e?.preventDefault();
    if (
      running.current ||
      uploadLock.current ||
      busy ||
      uploading ||
      (!(voice?.text ?? text).trim() && !pending.length && !prediction)
    )
      return;
    window.dispatchEvent(new Event("sire:stop-speech"));
    setVoiceReply(null);
    setError("");
    setBusy(true);
    outerBusy(true);
    running.current = true;
    const content = voice?.text ?? text;
    const ids = [
      ...new Set([
        ...pending.map((a) => a.id),
        ...(voice ? [voice.attachment_id] : []),
      ]),
    ];
    const inputAudio =
      voice?.attachment_id ??
      (pending.length === 1 &&
      pending[0].kind === "audio" &&
      pending[0].metadata.transcript?.text.trim() === content.trim()
        ? pending[0].id
        : undefined);
    setText("");
    setPending([]);
    setStage("Connecting to SIRE");
    const abort = new AbortController();
    controller.current = abort;
    job.current = crypto.randomUUID();
    let cid = id;
    let completedAssistant: string | null = null;
    let accepted = false;
    const markAccepted = () => {
      accepted = true;
      setUploads((items) =>
        items.map((item) =>
          item.status === "ready" &&
          item.attachment &&
          ids.includes(item.attachment.id)
            ? { ...item, status: "submitted" as const }
            : item,
        ),
      );
    };
    try {
      cid = await ensureConversation();
      if (mode === "investigate") {
        const submitted = await api<InvestigationJob>("/investigation-jobs", {
          conversation_id: cid,
          request_id: job.current,
          content,
          attachment_ids: ids,
          input_audio_id: inputAudio,
          mode,
          model,
          prediction_id: prediction,
          context: scope,
          voice_response: voiceMode,
        });
        markAccepted();
        setBackgroundSubmitted(submitted.id);
        setMode("chat");
        return;
      }
      setMessages((previous) => [
        ...previous,
        {
          id: `pending-${job.current}`,
          role: "user",
          content,
          status: "complete",
          metadata: { attachments: ids },
          created_at: new Date().toISOString(),
        },
        {
          id: "live-response",
          role: "assistant",
          content: "",
          status: "running",
          metadata: { tools: [], evidence: [], model },
          created_at: new Date().toISOString(),
        },
      ]);
      await streamMessage(
        {
          conversation_id: cid,
          request_id: job.current,
          content,
          attachment_ids: ids,
          input_audio_id: inputAudio,
          mode,
          model,
          prediction_id: prediction,
          facility_case_id: new URLSearchParams(location.search).get("case"),
          context: scope,
          voice_response: voiceMode,
          background_if_deep: true,
        },
        abort.signal,
        (event) => {
          if (conversation.current !== cid) return;
          if (event.type === "started") markAccepted();
          if (event.type === "investigation_job") {
            markAccepted();
            const accepted = event.job as InvestigationJob;
            setBackgroundSubmitted(accepted.id);
            setMode("chat");
            if (voiceMode)
              window.dispatchEvent(
                new CustomEvent("sire:voice-ack", {
                  detail:
                    "Your investigation request is saved. You can keep talking while it runs.",
                }),
              );
          }
          if (event.type === "plan") {
            const plan = event.plan as { intent: string };
            updateAssistant((row) => ({
              ...row,
              metadata: {
                ...row.metadata,
                orchestration: {
                  run_id: String(event.run_id),
                  intent: plan.intent,
                },
              },
            }));
          }
          if (event.type === "delta") {
            setStage("");
            updateAssistant((row) => ({
              ...row,
              content: row.content + String(event.text),
            }));
          }
          if (event.type === "tool") {
            if (event.status === "error" && event.message)
              setError(String(event.message));
            setStage(`${event.tool}: ${event.status}`);
            updateAssistant((row) => ({
              ...row,
              metadata: {
                ...row.metadata,
                tools: [
                  ...(row.metadata.tools ?? []),
                  event as unknown as Tool,
                ],
              },
            }));
          }
          if (event.type === "workspace") {
            const workspace = event.workspace as Workspace;
            setScope(workspace.context);
            updateAssistant((row) => ({
              ...row,
              metadata: { ...row.metadata, workspace },
            }));
          }
          if (event.type === "evidence")
            updateAssistant((row) => ({
              ...row,
              metadata: {
                ...row.metadata,
                evidence: event.evidence as Evidence[],
              },
            }));
          if (event.type === "report") {
            setStage("");
            updateAssistant((row) => ({
              ...row,
              content: String(event.content),
              metadata: {
                ...row.metadata,
                investigation: event.report as Investigation,
              },
            }));
          }
          if (event.type === "error") {
            setError(String(event.message));
            updateAssistant((row) => ({
              ...row,
              status: "error",
              metadata: {
                ...row.metadata,
                error: {
                  code: String(event.code),
                  message: String(event.message),
                },
              },
            }));
          }
          if (event.type === "done") {
            if (event.status === "complete" && event.assistant_message_id)
              completedAssistant = String(event.assistant_message_id);
          }
          if (event.type === "done")
            updateAssistant((row) => ({
              ...row,
              status: String(event.status),
              metadata: event.metadata as Meta,
            }));
        },
      );
      setPrediction(null);
    } catch (e) {
      if (
        !accepted &&
        !voice &&
        conversation.current === cid &&
        !abort.signal.aborted
      ) {
        setText(content);
        setPending(pending);
      }
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
      else updateAssistant((row) => ({ ...row, status: "cancelled" }));
    } finally {
      running.current = false;
      setBusy(false);
      outerBusy(false);
      setStage("");
      refresh();
      if (cid && conversation.current === cid) {
        try {
          const d = await api<Detail>(`/conversations/${cid}`);
          if (conversation.current !== cid) return;
          setMessages(d.messages);
          setAttachments(d.attachments);
          if (voiceMode && completedAssistant)
            setVoiceReply(completedAssistant);
        } catch (e) {
          setError((e as Error).message);
        }
      }
    }
  }
  async function stop(
    reason:
      | "operator_stop"
      | "voice_user_interrupt"
      | "voice_new_turn"
      | "voice_session_stop" = "operator_stop",
  ) {
    await api("/chat/cancel", { request_id: job.current, reason }).catch(
      () => {},
    );
    controller.current?.abort();
    setStage("Cancellation requested; an active tool may finish.");
  }
  function key(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }
  function spokenReply(message: Message): string {
    if (!voiceMode) return message.content;
    if (message.metadata.speech_text) return message.metadata.speech_text;
    if (message.metadata.investigation)
      return `The investigation returned ${message.metadata.investigation.hypotheses.length} proposed mechanisms. They remain unverified. Review the evidence and suggested checks in the chat.`;
    if (message.metadata.measurement_profiles) {
      const count = message.metadata.measurement_profiles.reduce(
        (sum, profile) => sum + profile.groups.length,
        0,
      );
      return `Source statistics are ready for ${count} measurement channels. The exact values and source references are in this chat. A physical cause is not confirmed.`;
    }
    return message.content;
  }
  const inspectedMeta =
    (
      messages.find((m) => m.id === inspected) ||
      [...messages].reverse().find((m) => m.role === "assistant")
    )?.metadata || null;
  return (
    <div className={`chat-workspace ${inspector ? "inspector-open" : ""}`}>
      <section
        className="chat-view"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!busy && !uploading)
            void upload(Array.from(e.dataTransfer.files));
        }}
      >
        <div className="chat-context-bar">
          <button
            type="button"
            className="secondary"
            aria-expanded={inspector}
            onClick={() => setInspector(!inspector)}
          >
            Engineering & evidence
          </button>
          {scope ? (
            <span className="source-label">
              SIMULATED · {scope.asset_id} · {scope.as_of}
            </span>
          ) : (
            <span className="muted">
              General conversation · attach evidence when needed
            </span>
          )}
        </div>
        <div className="messages" role="log" aria-live="polite">
          <div className="message-width">
            {messages.length === 0 &&
              !busy &&
              (welcome ?? (
                <div className="empty-chat">
                  <div className="sire-symbol">S</div>
                  <h1>What would you like to investigate?</h1>
                  <p>Ask a question, explain a symptom, or attach evidence.</p>
                  <div className="quick-prompts">
                    {[
                      "Explain how remaining useful life is estimated.",
                      "What evidence helps investigate bearing wear?",
                    ].map((q) => (
                      <button key={q} onClick={() => setText(q)}>
                        {q}
                        <span>↗</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            {messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                <div className="message-label">
                  {message.role === "user" ? "You" : "SIRE"}
                  <time>
                    {new Date(message.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </div>
                {message.metadata.attachments?.map((identifier) => {
                  const a = attachments.find((x) => x.id === identifier);
                  return a ? (
                    <div className="attachment-preview" key={a.id}>
                      <a
                        href={`/api/v1/attachments/${a.id}/content`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {a.kind === "image" && (
                          <img
                            src={`/api/v1/attachments/${a.id}/content`}
                            alt={a.name}
                          />
                        )}
                        <span>{a.name}</span>
                      </a>
                      {a.kind === "video" && (
                        <video
                          controls
                          preload="none"
                          style={{ maxWidth: "100%" }}
                          src={`/api/v1/attachments/${a.id}/content`}
                          aria-label={`Video ${a.name}`}
                        />
                      )}
                      {a.kind === "audio" && (
                        <audio
                          controls
                          preload="none"
                          src={`/api/v1/attachments/${a.id}/content`}
                          aria-label={`Recording ${a.name}`}
                        />
                      )}
                    </div>
                  ) : null;
                })}
                <div className="markdown">
                  <Markdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      img: ({ src, alt }) =>
                        src?.startsWith("/api/v1/attachments/") ? (
                          <img src={src} alt={alt ?? "Attached evidence"} />
                        ) : (
                          <span>{alt || "External image omitted"}</span>
                        ),
                      a: ({ href, children }) =>
                        href?.startsWith("#source=") ? (
                          <button
                            type="button"
                            className="citation-button"
                            onClick={() => {
                              setInspected(message.id);
                              setRequestedSource({
                                id: decodeURIComponent(href.slice(8)),
                                nonce: performance.now(),
                              });
                              setInspector(true);
                            }}
                          >
                            {children}
                          </button>
                        ) : (
                          <a href={href}>{children}</a>
                        ),
                    }}
                  >
                    {citationLinks(message.content)}
                  </Markdown>
                </div>
                {message.status === "running" && !message.content && (
                  <span className="working">
                    {stage || "Generating response…"}
                  </span>
                )}
                {message.role === "assistant" &&
                  message.status === "complete" &&
                  message.content &&
                  speechEnabled && (
                    <ReadReply
                      volume={audioPreferences?.playbackVolume}
                      speakerId={audioPreferences?.speakerId}
                      text={spokenReply(message)}
                      disabled={busy || uploading}
                      autoSpeak={voiceMode && voiceReply === message.id}
                    />
                  )}
                {message.status === "partial" && (
                  <p className="limit-note">
                    Partial response: some requested evidence or tools were
                    unavailable. Inspect the actual trace for details.
                  </p>
                )}
                {message.status === "cancelled" && (
                  <div className="muted">
                    Response stopped. Any partial text is retained.
                  </div>
                )}
                {message.metadata.error && (
                  <div className="error">{message.metadata.error.message}</div>
                )}
                {message.role === "assistant" &&
                  (message.metadata.tools?.some(
                    (tool) =>
                      tool.tool !== "conversation.respond" &&
                      tool.tool !== "llm.chat",
                  ) ||
                    message.metadata.evidence?.length ||
                    message.metadata.investigation) && (
                    <>
                      <button
                        className="text-button"
                        onClick={() => {
                          setInspected(message.id);
                          setInspector(true);
                        }}
                      >
                        Inspect evidence and tools
                      </button>
                      <Trace meta={message.metadata} />
                    </>
                  )}
              </article>
            ))}
            <div ref={bottom} />
          </div>
        </div>
        <div className="composer-wrap">
          <div className="composer-width">
            <BackgroundInvestigation
              conversationId={id}
              submitted={backgroundSubmitted}
              onFinished={async (completed) => {
                if (
                  conversation.current !== completed.conversation_id ||
                  running.current ||
                  uploadLock.current
                )
                  return;
                try {
                  const detail = await api<Detail>(
                    `/conversations/${completed.conversation_id}`,
                  );
                  if (conversation.current === completed.conversation_id) {
                    setMessages(detail.messages);
                    setAttachments(detail.attachments);
                    refresh();
                  }
                } catch (reason) {
                  setError((reason as Error).message);
                }
              }}
            />
            {error && (
              <div role="alert" className="error">
                {error}
                <button onClick={() => setError("")} aria-label="Dismiss error">
                  ×
                </button>
              </div>
            )}
            {stage && busy && (
              <div role="status" className="stage">
                <span className="pulse" />
                {stage}
              </div>
            )}
            {liveVoice && (
              <>
                <label className="voice-mode">
                  <input
                    type="checkbox"
                    checked={voiceMode}
                    onChange={(event) => {
                      setVoiceMode(event.target.checked);
                      if (!event.target.checked) {
                        setVoiceReply(null);
                        window.dispatchEvent(new Event("sire:stop-speech"));
                      }
                    }}
                  />
                  Read spoken replies automatically
                </label>
                <VoiceSession
                  microphoneId={audioPreferences?.microphoneId}
                  speakerId={audioPreferences?.speakerId}
                  volume={audioPreferences?.playbackVolume}
                  disabled={uploading}
                  getConversation={ensureConversation}
                  onActive={() => setVoiceMode(true)}
                  onSpeech={() => {
                    window.dispatchEvent(new Event("sire:stop-speech"));
                    if (running.current) void stop("voice_user_interrupt");
                  }}
                  onStop={() => {
                    setVoiceMode(false);
                    setVoiceReply(null);
                    if (running.current) void stop("voice_session_stop");
                  }}
                  onTurn={async (turn) => {
                    if (uploadLock.current || pending.length >= 6)
                      throw new Error(
                        "Finish the upload or remove an attachment before sending this voice turn.",
                      );
                    if (running.current) {
                      await stop("voice_new_turn");
                      const deadline = performance.now() + 3000;
                      while (running.current && performance.now() < deadline)
                        await new Promise((resolve) => setTimeout(resolve, 25));
                      if (running.current)
                        throw new Error(
                          "The previous response is still stopping.",
                        );
                    }
                    const cid = conversation.current;
                    if (!cid)
                      throw new Error("Conversation is no longer available.");
                    const detail = await api<Detail>(`/conversations/${cid}`);
                    if (conversation.current !== cid)
                      throw new Error(
                        "Conversation changed; voice turn was not sent.",
                      );
                    setAttachments(detail.attachments);
                    await send(undefined, turn);
                  }}
                />
                <RecordVoice
                  microphoneId={audioPreferences?.microphoneId}
                  key={id ?? "new"}
                  disabled={uploading || pending.length >= 6}
                  onStart={() => {
                    window.dispatchEvent(new Event("sire:stop-speech"));
                    if (busy) void stop();
                  }}
                  onRecording={(file, requestId) => upload([file], requestId)}
                />
              </>
            )}
            <div
              className="upload-queue"
              aria-label="Attachment status"
              aria-live="polite"
            >
              {uploads.map((row) => (
                <div className={`upload-row ${row.status}`} key={row.key}>
                  <div>
                    <strong>{row.file.name}</strong>
                    <small>
                      {row.file.size.toLocaleString()} bytes ·{" "}
                      {row.file.type || "Type checked by server"} ·{" "}
                      {row.status === "uploading"
                        ? "Uploading and parsing"
                        : row.status.replaceAll("_", " ")}
                      {row.elapsedMs !== undefined
                        ? ` · ${(row.elapsedMs / 1000).toFixed(2)}s`
                        : ""}
                    </small>
                    {row.error && (
                      <span role="alert" className="error">
                        {row.error}
                      </span>
                    )}
                  </div>
                  {(row.status === "failed" || row.status === "cancelled") && (
                    <button
                      type="button"
                      disabled={busy || uploading}
                      onClick={() => upload([row.file], row.mediaId, row.key)}
                    >
                      Retry
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label={`${row.status === "uploading" ? "Cancel" : "Remove"} ${row.file.name}`}
                    onClick={() => removeUpload(row)}
                  >
                    {row.status === "uploading" ? "Cancel" : "Remove"}
                  </button>
                </div>
              ))}
            </div>
            <form className="composer" onSubmit={send}>
              <div className="pending">
                {new URLSearchParams(location.search).get("case") && (
                  <span className="chip">
                    Explicit saved simulation case attached
                  </span>
                )}
                {pending.map((a) => (
                  <span className="chip" key={a.id}>
                    {a.name}
                    <button
                      type="button"
                      aria-label={`Remove ${a.name}`}
                      onClick={() =>
                        setPending((p) => p.filter((x) => x.id !== a.id))
                      }
                    >
                      ×
                    </button>
                  </span>
                ))}
                {prediction && (
                  <span className="chip">
                    Explicit prediction result attached
                    <button
                      type="button"
                      aria-label="Remove prediction"
                      onClick={() => setPrediction(null)}
                    >
                      ×
                    </button>
                  </span>
                )}
              </div>
              <textarea
                aria-label="Message SIRE"
                placeholder="Message SIRE…"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={key}
                maxLength={8000}
                disabled={busy}
              />
              <div className="composer-tools">
                <input
                  ref={file}
                  hidden
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md,.csv,.json,.docx,.xlsx,image/jpeg,image/png,image/webp,.wav,.flac,.ogg,.mp3,.mp4,.mov,.avi,.webm,.mkv"
                  onChange={(e) => {
                    const selected = Array.from(e.currentTarget.files ?? []);
                    e.currentTarget.value = "";
                    if (selected.length) void upload(selected);
                  }}
                />
                <input
                  ref={camera}
                  hidden
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(e) => {
                    const selected = Array.from(e.currentTarget.files ?? []);
                    e.currentTarget.value = "";
                    if (selected.length) void upload(selected);
                  }}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Attach images or documents"
                  disabled={busy || uploading}
                  onClick={() => file.current?.click()}
                >
                  <Paperclip size={18} />
                </button>
                <button
                  type="button"
                  className="icon-button camera"
                  aria-label="Take or choose photo"
                  disabled={busy || uploading}
                  onClick={() => camera.current?.click()}
                >
                  <Camera size={18} />
                </button>
                <button
                  className={`mode-button ${mode === "investigate" ? "selected" : ""}`}
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    setMode(mode === "chat" ? "investigate" : "chat")
                  }
                >
                  {mode === "chat" ? "◇ Investigate" : "◇ Investigation on"}
                </button>
                <span className="composer-spacer" />
                {uploading ? (
                  <span className="muted">Validating upload…</span>
                ) : busy ? (
                  <button
                    className="send stop"
                    type="button"
                    aria-label="Stop response"
                    onClick={() => void stop()}
                  >
                    <Square size={15} />
                  </button>
                ) : (
                  <button
                    className="send"
                    aria-label="Send message"
                    disabled={!text.trim() && !pending.length && !prediction}
                  >
                    <ArrowUp size={19} />
                  </button>
                )}
              </div>
            </form>
            <p className="composer-note">
              Local inference · files are stored with your chat · Enter sends,
              Shift+Enter adds a line
            </p>
          </div>
        </div>
      </section>
      {inspector && (
        <Suspense
          fallback={
            <aside className="inspector" role="status">
              Loading source tools…
            </aside>
          }
        >
          <Inspector
            requestedSource={requestedSource}
            scope={scope}
            setScope={setScope}
            meta={inspectedMeta}
            attachments={attachments}
            busy={busy || uploading}
            close={() => setInspector(false)}
            prompt={(value) => {
              setText(value);
              setInspector(true);
            }}
            selectAttachment={(value) => {
              const found = attachments.find((item) => item.id === value);
              if (found) {
                if (pending.some((item) => item.id === value)) return;
                if (
                  pending.length >= 6 ||
                  (found.kind === "image" &&
                    pending.filter((item) => item.kind === "image").length >= 3)
                ) {
                  setError(
                    "Remove an attachment before selecting another; at most six files and three images can be sent.",
                  );
                  return;
                }
                setPending((items) => [...items, found]);
              }
            }}
            attachPrediction={(value) => {
              setPrediction(value);
              setText("Explain this saved model result and its limitations.");
            }}
          />
        </Suspense>
      )}
    </div>
  );
}

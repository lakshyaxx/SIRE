import { useEffect, useRef, useState } from "react";
import { api, type InvestigationJob } from "../../lib/api";

/** Reject stale polling snapshots after a terminal job state. */
export function acceptJobUpdate(
  current: InvestigationJob | null,
  incoming: InvestigationJob | null,
): InvestigationJob | null {
  if (!incoming || !current || current.id !== incoming.id) return incoming;
  if (
    !["queued", "running"].includes(current.status) &&
    ["queued", "running"].includes(incoming.status)
  )
    return current;
  if (
    incoming.updated_at &&
    current.updated_at &&
    Date.parse(incoming.updated_at) < Date.parse(current.updated_at)
  )
    return current;
  return incoming;
}

/** Display durable actual progress while leaving the normal chat composer available. */
export function BackgroundInvestigation({
  conversationId,
  submitted,
  onFinished,
}: {
  conversationId: string | null;
  submitted: string | null;
  onFinished: (job: InvestigationJob) => void;
}) {
  const [job, setJob] = useState<InvestigationJob | null>(null);
  const [error, setError] = useState("");
  const latest = useRef<InvestigationJob | null>(null);
  const finished = useRef("");
  const callback = useRef(onFinished);
  callback.current = onFinished;
  function commit(incoming: InvestigationJob | null) {
    const accepted = acceptJobUpdate(latest.current, incoming);
    latest.current = accepted;
    setJob(accepted);
    return accepted;
  }
  useEffect(() => {
    latest.current = null;
    setJob(null);
    setError("");
    if (!conversationId) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let sawActive = false;
    const abort = new AbortController();
    async function read() {
      try {
        const jobs = await api<InvestigationJob[]>(
          `/investigation-jobs?conversation_id=${encodeURIComponent(conversationId!)}`,
          undefined,
          undefined,
          abort.signal,
        );
        if (!live) return;
        const current = commit(
          jobs.find((item) => item.id === submitted) || jobs[0] || null,
        );
        if (current) {
          if (["queued", "running"].includes(current.status)) {
            sawActive = true;
            timer = setTimeout(read, 1000);
          } else if (
            (sawActive || current.id === submitted) &&
            finished.current !== current.id
          ) {
            finished.current = current.id;
            callback.current(current);
          }
        }
      } catch (reason) {
        if (live) setError((reason as Error).message);
      }
    }
    void read();
    return () => {
      live = false;
      abort.abort();
      if (timer) clearTimeout(timer);
    };
  }, [conversationId, submitted]);
  const active = job && ["queued", "running"].includes(job.status);
  const step = active
    ? job?.events.filter((event) => event.type === "tool").at(-1)
    : null;
  const facts = job?.events
    .filter(
      (event) =>
        event.type === "delta" &&
        event.source === "validated_descriptive_measurement_statistics",
    )
    .map((event) => String(event.text))
    .join("\n");
  return (
    <>
      {job && (
        <div className="stage" role="status">
          Investigation: {job.status}
          {step ? ` · ${String(step.tool)}: ${String(step.status)}` : ""}
          {active && (
            <>
              <span> · You can continue this conversation.</span>
              <button
                type="button"
                onClick={() =>
                  api<InvestigationJob>(
                    `/investigation-jobs/${job.id}/cancel?conversation_id=${encodeURIComponent(job.conversation_id)}`,
                    {},
                  )
                    .then((value) => {
                      if (latest.current?.id === value.id) commit(value);
                    })
                    .catch((reason) => setError(reason.message))
                }
              >
                Stop investigation
              </button>
            </>
          )}
          {job.error && <span role="alert">{job.error.message}</span>}
        </div>
      )}
      {facts && (
        <details>
          <summary>Verified intermediate source statistics</summary>
          <pre style={{ whiteSpace: "pre-wrap" }}>{facts}</pre>
          <small>
            Exact uploaded-source statistics; physical association and cause
            remain unverified.
          </small>
        </details>
      )}
      {job?.events_trimmed ? (
        <small>
          Recent progress events only; the full saved result and tool trace
          remain available.
        </small>
      ) : null}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </>
  );
}

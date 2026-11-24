import {
  Check,
  Clipboard,
  Download,
  ExternalLink,
  Link2,
  Square,
  X,
} from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Link, useParams } from "react-router";
import { SireIdentity } from "@/components/SireIdentity";
import { AudioPlayer } from "@/components/AudioPlayer";
import { CapabilityGate } from "@/components/CapabilityGate";
import {
  Button,
  Card,
  LoadingRows,
  PageHeader,
  StatePanel,
} from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { usePreferences } from "@/hooks/usePreferences";
import { useRemote } from "@/hooks/useRemote";
import { api } from "@/services/api";
import type { InvestigationDetail, SourceLink } from "@/types/api";
import Markdown from "react-markdown";
import { citationLinks } from "../lib/citations";
import { api as coreApi } from "../lib/api";

type Tab = "findings" | "evidence" | "data" | "activity";

function EvidenceText({ text }: { text: string }) {
  return (
    <Markdown
      components={{
        img: ({ alt }) => <span>{alt || "Image reference"}</span>,
        a: ({ href, children }) => {
          if (href?.startsWith("#source=")) {
            try {
              return (
                <Link
                  to={`/evidence?evidence=${encodeURIComponent(decodeURIComponent(href.slice(8)))}`}
                >
                  {children}
                </Link>
              );
            } catch {
              return <span>{children}</span>;
            }
          }
          return (
            <a href={href} rel="noreferrer">
              {children}
            </a>
          );
        },
      }}
    >
      {citationLinks(text)}
    </Markdown>
  );
}

export function InvestigationWorkspace() {
  const { id = "" } = useParams();
  const { capabilities } = useApi();
  const { preferences } = usePreferences();
  const [tab, setTab] = useState<Tab>("findings");
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const detail = useRemote((signal) => api.investigation(id, signal), [id]);
  const [trace, setTrace] = useState<unknown>(null);
  const [traceError, setTraceError] = useState("");
  useEffect(() => {
    setTrace(null);
    setTraceError("");
  }, [id]);
  useEffect(() => {
    if (!detail.data || !["queued", "running"].includes(detail.data.status))
      return;
    const timer = setTimeout(detail.reload, 1200);
    return () => clearTimeout(timer);
  }, [detail.data, detail.reload]);

  async function copySummary() {
    if (!detail.data?.summary) return;
    try {
      await navigator.clipboard.writeText(detail.data.summary);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setActionError("Clipboard access was denied by the browser.");
    }
  }
  async function exportReport() {
    setActionError(null);
    try {
      const blob = await api.exportInvestigation(id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `investigation-${id}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "Export failed.",
      );
    }
  }
  async function cancel() {
    setActionError(null);
    try {
      await api.cancelInvestigation(id);
      detail.reload();
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "Cancellation failed.",
      );
    }
  }

  if (detail.loading)
    return (
      <>
        <PageHeader
          title="Investigation Workspace"
          description="Loading the investigation record."
        />
        <LoadingRows count={8} />
      </>
    );
  if (detail.error || !detail.data)
    return (
      <>
        <PageHeader
          title="Investigation Workspace"
          description="Investigation Findings and evidence will appear when the record is available."
        />
        <StatePanel
          kind="error"
          title="Investigation unavailable"
          message={detail.error ?? "No investigation was returned."}
        />
      </>
    );
  const item = detail.data;

  return (
    <>
      <PageHeader
        eyebrow={`Investigation · ${item.status}`}
        title={item.title}
        description={item.question}
        actions={
          <>
            <Button
              variant="secondary"
              onClick={copySummary}
              disabled={!item.summary}
              title={
                !item.summary
                  ? "No investigation summary is available."
                  : undefined
              }
            >
              {copied ? <Check size={16} /> : <Clipboard size={16} />}{" "}
              {copied ? "Copied" : "Copy summary"}
            </Button>
            {capabilities?.authorization.canExportInvestigations &&
              item.caseId && (
                <Button variant="secondary" onClick={exportReport}>
                  <Download size={16} /> Export
                </Button>
              )}
            {(item.status === "running" || item.status === "queued") && (
              <Button variant="danger" onClick={cancel}>
                <Square size={14} /> Cancel run
              </Button>
            )}
          </>
        }
      />
      {actionError && (
        <StatePanel kind="error" title="Action failed" message={actionError} />
      )}
      {item.error && (
        <StatePanel
          kind="error"
          title={investigationNoticeTitle(item.status, item.error.stage)}
          message={`${item.error.message} Error code: ${item.error.code}.`}
        />
      )}
      {copied && (
        <p className="success-notice" role="status">
          <Check size={15} aria-hidden="true" /> Summary copied to clipboard.
        </p>
      )}
      {item.status === "running" && (
        <StatePanel
          kind="loading"
          title="SIRE is reviewing your information"
          message="Following actual tool events. This page updates automatically."
          action={
            <Button variant="secondary" onClick={detail.reload}>
              Refresh
            </Button>
          }
        />
      )}
      <Card title="Investigation context" className="investigation-context">
        <div className="definition-list">
          <div>
            <dt>Case ID</dt>
            <dd>{item.caseId ?? item.id}</dd>
          </div>
          <div>
            <dt>Asset</dt>
            <dd>
              {item.assetId ?? "Not provided"}
              {item.assetIdentitySource && (
                <small>
                  {" "}
                  ·{" "}
                  {item.assetIdentitySource === "user_question"
                    ? "User-requested identity; not independently verified"
                    : "Source-declared identity; not independently verified"}
                </small>
              )}
            </dd>
          </div>
          <div>
            <dt>Incident time</dt>
            <dd>
              {item.incidentAt
                ? new Date(item.incidentAt).toLocaleString()
                : "Not provided"}
            </dd>
          </div>
          <div>
            <dt>Processing stage</dt>
            <dd>{item.stage ?? item.status}</dd>
          </div>
        </div>
        {!!item.attachments?.length && (
          <div>
            <h3>Submitted source files</h3>
            <ul>
              {item.attachments.map((file) => (
                <li key={file.id}>
                  <Link
                    to={`/evidence?evidence=${encodeURIComponent(file.id)}`}
                  >
                    {file.name}
                  </Link>{" "}
                  · {file.kind}
                  {file.missing ? " · source unavailable" : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      <div
        className="workspace-tabs"
        role="tablist"
        aria-label="Investigation sections"
      >
        {(["findings", "evidence", "data", "activity"] as Tab[]).map(
          (value) => (
            <button
              key={value}
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
            >
              {value}
            </button>
          ),
        )}
      </div>
      <CapabilityGate
        capability="investigations"
        title="Investigation Workspace"
      >
        {tab === "findings" && <Findings detail={item} />}
        {tab === "evidence" && <LinkedEvidence detail={item} />}
        {tab === "data" && <DataSummary detail={item} />}
        {tab === "activity" && <ActivityLog detail={item} />}
      </CapabilityGate>
      <Card title="Continue and inspect">
        <div className="row-actions">
          {item.conversationId && (
            <Link
              className="button button-secondary"
              to={`/chat/${item.conversationId}`}
            >
              Continue this conversation
            </Link>
          )}
          {item.runId && (
            <Button
              variant="secondary"
              onClick={() => {
                setTraceError("");
                coreApi(`/runs/${encodeURIComponent(item.runId!)}/trace`)
                  .then(setTrace)
                  .catch((reason) => setTraceError(reason.message));
              }}
            >
              Inspect execution trace
            </Button>
          )}
        </div>
        {traceError && (
          <p role="alert" className="error">
            {traceError}
          </p>
        )}
        {trace !== null && (
          <details className="trace" open>
            <summary>Actual tools, models and source references</summary>
            <pre>{JSON.stringify(trace, null, 2)}</pre>
          </details>
        )}
        {item.rawReport !== undefined && (
          <details className="trace">
            <summary>
              Source statistics, exclusions and verification record
            </summary>
            <pre>{JSON.stringify(item.rawReport, null, 2)}</pre>
          </details>
        )}
      </Card>
      {preferences.audioEnabled &&
        capabilities?.kokoro.state === "available" &&
        item.summary && (
          <Card title="Kokoro Speech" className="audio-card">
            <AudioPlayer
              text={[item.summary, item.uncertainty]
                .filter(Boolean)
                .join(" ")
                .slice(0, 1100)}
            />
          </Card>
        )}
      <div className="bottom-actions">
        <Link to="/cases" className="button button-ghost">
          <X size={15} /> Close workspace
        </Link>
      </div>
    </>
  );
}

export function investigationNoticeTitle(
  status: string,
  stage?: string,
): string {
  return `${status === "partial" ? "Partial investigation" : "Investigation failed"} · ${stage ?? "stage not recorded"}`;
}

export function Findings({ detail }: { detail: InvestigationDetail }) {
  return (
    <div className="workspace-split">
      <div className="findings-column">
        <Card title="What I found" action={<SireIdentity compact />}>
          {detail.explanations?.plain && (
            <p className="prose-lead">{detail.explanations.plain}</p>
          )}
          <h3>Investigation summary</h3>
          {detail.summary ? (
            <p className="prose-lead">{detail.summary}</p>
          ) : (
            <EmptySection label="No investigation summary is available." />
          )}
          <h3>Observations</h3>
          {detail.observations.length ? (
            detail.observations.map((value) => (
              <Finding
                key={value.id}
                text={value.text}
                sources={value.sources}
                meta={value.classification}
              />
            ))
          ) : (
            <EmptySection label="No findings have been provided yet." />
          )}
        </Card>
        <LinkedEvidence detail={detail} />
        <div className="two-column">
          <Card title="Possible causes">
            {detail.possibleCauses.length ? (
              detail.possibleCauses.map((value) => (
                <Finding
                  key={value.id}
                  text={value.text}
                  sources={value.sources}
                  meta={value.confidence}
                />
              ))
            ) : (
              <EmptySection label="No Possible Causes are available." />
            )}
          </Card>
          <Card title="What you should check next">
            {detail.recommendations.length ? (
              detail.recommendations.map((value) => (
                <Finding
                  key={value.id}
                  text={value.text}
                  sources={value.sources}
                  meta={value.priority}
                />
              ))
            ) : (
              <EmptySection label="No recommendations are available." />
            )}
            <h3>Follow-up questions</h3>
            {detail.followUps.length ? (
              <ol className="number-list">
                {detail.followUps.map((value) => (
                  <li key={value}>
                    <EvidenceText text={value} />
                  </li>
                ))}
              </ol>
            ) : (
              <EmptySection label="No follow-up questions have been provided." />
            )}
          </Card>
        </div>
        <Card title="Competing hypotheses">
          {detail.hypotheses?.length ? (
            <div className="hypothesis-list">
              {detail.hypotheses.map((hypothesis) => (
                <HypothesisCard key={hypothesis.id} hypothesis={hypothesis} />
              ))}
            </div>
          ) : (
            <StatePanel
              kind="gated"
              title="Incomplete analysis"
              message="No competing hypotheses, supporting evidence, contradictory evidence or missing-information record was provided."
            />
          )}
        </Card>
      </div>
      <aside className="evidence-column">
        <Card title="Limitations and uncertainty">
          {detail.uncertainty ? (
            <p>{detail.uncertainty}</p>
          ) : (
            <EmptySection label="No uncertainty statement is available." />
          )}
        </Card>
        {(detail.explanations?.technical || detail.interpretation) && (
          <details className="card engineering-details">
            <summary>Engineering details</summary>
            <div>
              <h3>Technical explanation</h3>
              {detail.explanations?.technical ? (
                <p>{detail.explanations.technical}</p>
              ) : (
                <EmptySection label="No technical explanation has been provided." />
              )}
              <h3>Qwen analysis</h3>
              {detail.interpretation ? (
                <>
                  <p>{detail.interpretation}</p>
                  <p className="ai-notice">
                    Qwen analysis is an interpretation and must be reviewed
                    against supporting evidence.
                  </p>
                </>
              ) : (
                <EmptySection label="No Qwen analysis has been provided." />
              )}
            </div>
          </details>
        )}
      </aside>
    </div>
  );
}

function HypothesisCard({
  hypothesis,
}: {
  hypothesis: NonNullable<InvestigationDetail["hypotheses"]>[number];
}) {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  return (
    <article className="hypothesis-card">
      <header>
        <div>
          <span
            className={`classification classification-${hypothesis.classification}`}
          >
            {hypothesis.classification.replace("-", " ")}
          </span>
          <h3>{hypothesis.title}</h3>
        </div>
        <Button
          variant="ghost"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Collapse hypothesis" : "Expand hypothesis"}
        </Button>
      </header>
      {hypothesis.mechanism && (
        <div className="evidence-prose">
          <EvidenceText text={hypothesis.mechanism} />
        </div>
      )}
      <div
        id={panelId}
        className={`evidence-expansion ${expanded ? "is-expanded" : ""}`}
        aria-hidden={!expanded}
        inert={!expanded}
      >
        <div className="evidence-expansion-inner">
          <div className="hypothesis-detail">
            <EvidenceGroup
              title="Supporting Evidence"
              sources={hypothesis.supportingEvidence}
            />
            <EvidenceGroup
              title="Contradictory Evidence"
              sources={hypothesis.contradictoryEvidence}
            />
            {!!hypothesis.assumptions?.length && (
              <EvidenceGroup
                title="Unverified assumptions"
                items={hypothesis.assumptions}
              />
            )}
            {!!hypothesis.expectedSigns?.length && (
              <EvidenceGroup
                title="Expected signs · not observations"
                items={hypothesis.expectedSigns}
              />
            )}
            {!!hypothesis.missingInformation.length && (
              <EvidenceGroup
                title="Missing information"
                items={hypothesis.missingInformation}
              />
            )}
            <EvidenceGroup
              title="Diagnostic Checks"
              items={hypothesis.recommendedChecks}
            />
            {hypothesis.rankingRationale && (
              <div>
                <h4>Ranking rationale</h4>
                <p>{hypothesis.rankingRationale}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function EvidenceGroup({
  title,
  items = [],
  sources = [],
}: {
  title: string;
  items?: string[];
  sources?: SourceLink[];
}) {
  return (
    <div>
      <h4>{title}</h4>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : sources.length ? (
        <SourceLinks sources={sources} />
      ) : (
        <p className="empty-copy">
          {title === "Contradictory Evidence"
            ? "No contradiction established from the supplied evidence."
            : "Not provided."}
        </p>
      )}
    </div>
  );
}

function Finding({
  text,
  sources,
  meta,
}: {
  text: string;
  sources: Array<{ evidenceId: string; label: string; locator?: string }>;
  meta?: string;
}) {
  return (
    <article className="finding">
      <div>
        {meta && <span className="finding-meta">{meta}</span>}
        <div className="evidence-prose">
          {text.length > 500 ? (
            <>
              <EvidenceText
                text={text.slice(0, 480).replace(/\s+\S*$/, "") + "…"}
              />
              <details>
                <summary>Excerpt shown · read full source observation</summary>
                <EvidenceText text={text} />
              </details>
            </>
          ) : (
            <EvidenceText text={text} />
          )}
        </div>
      </div>
      {sources.length > 0 && <SourceLinks sources={sources} />}
    </article>
  );
}
function SourceLinks({ sources }: { sources: SourceLink[] }) {
  return (
    <div className="source-links">
      {sources.map((source) => (
        <Link
          key={`${source.evidenceId}-${source.locator}`}
          to={`/evidence?evidence=${encodeURIComponent(source.evidenceId)}`}
        >
          <Link2 size={12} /> {source.label}
          {source.locator && source.locator !== source.label
            ? ` · ${source.locator}`
            : ""}
        </Link>
      ))}
    </div>
  );
}
function EmptySection({ label }: { label: string }) {
  return <p className="empty-copy">{label}</p>;
}
function LinkedEvidence({ detail }: { detail: InvestigationDetail }) {
  const links = [
    ...detail.observations,
    ...detail.possibleCauses,
    ...detail.recommendations,
  ].flatMap((item) => item.sources);
  const hypothesisLinks = (detail.hypotheses ?? []).flatMap((item) => [
    ...item.supportingEvidence,
    ...item.contradictoryEvidence,
  ]);
  const unique = Array.from(
    new Map(
      [...links, ...hypothesisLinks].map((item) => [item.evidenceId, item]),
    ).values(),
  );
  return (
    <Card title="Source references">
      {unique.length ? (
        <div className="link-list">
          {unique.map((item) => (
            <Link
              key={`${item.evidenceId}-${item.label}-${item.locator ?? ""}`}
              to={`/evidence?evidence=${encodeURIComponent(item.evidenceId)}`}
            >
              <Link2 size={16} />
              <span>
                <strong>{item.label}</strong>
                {item.locator && item.locator !== item.label && (
                  <small>{item.locator}</small>
                )}
              </span>
              <ExternalLink size={14} />
            </Link>
          ))}
        </div>
      ) : (
        <StatePanel
          kind="empty"
          title="No supporting evidence has been added yet"
          message="Evidence links will appear when they are included in the investigation."
        />
      )}
    </Card>
  );
}
function DataSummary({ detail }: { detail: InvestigationDetail }) {
  return (
    <Card title="Investigation data">
      <div className="definition-list">
        <div>
          <dt>Evidence records</dt>
          <dd>{detail.evidenceCount}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{new Date(detail.createdAt).toLocaleString()}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{new Date(detail.updatedAt).toLocaleString()}</dd>
        </div>
        <div>
          <dt>State</dt>
          <dd>{detail.status}</dd>
        </div>
      </div>
    </Card>
  );
}
function ActivityLog({ detail }: { detail: InvestigationDetail }) {
  return (
    <Card title="Activity">
      {detail.activity.length ? (
        <ol className="timeline">
          {detail.activity.map((item) => (
            <li key={item.id}>
              <span />
              <div>
                <time>
                  {item.at
                    ? new Date(item.at).toLocaleString()
                    : "Event time not recorded"}
                </time>
                <p>{item.message}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <StatePanel
          kind="empty"
          title="No activity recorded"
          message="No activity has been recorded for this investigation."
        />
      )}
    </Card>
  );
}

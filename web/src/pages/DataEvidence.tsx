import {
  ArrowLeft,
  ArrowRight,
  FileImage,
  FileText,
  RefreshCw,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import {
  Button,
  Card,
  DefinitionList,
  LoadingRows,
  PageHeader,
  StatePanel,
} from "../components/ui";
import { useRemote } from "../hooks/useRemote";
import { api, referenceAttachmentId } from "../services/api";
import type { EvidenceItem } from "../types/api";

/** Paginated real uploads plus exact canonical source lookup, including off-page citations. */
export function DataEvidence() {
  const [params, setParams] = useSearchParams();
  const requested = params.get("evidence");
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<EvidenceItem | null>(null);
  const [source, setSource] = useState<unknown>(null);
  const [sourceError, setSourceError] = useState("");
  const list = useRemote(
    (signal) => api.evidence(signal, page, query, kind),
    [page, query, kind],
  );
  const sections = useRemote(
    (signal) =>
      selected?.conversationId
        ? api.attachmentSections(selected.conversationId, signal)
        : Promise.resolve(null),
    [selected?.id],
  );
  useEffect(() => {
    if (!requested && list.data) setSelected(list.data.items[0] ?? null);
  }, [list.data, requested]);
  useEffect(() => {
    setZoom(1);
    setSource(null);
    setSourceError("");
    if (!requested) return;
    const abort = new AbortController();
    setSelected(null);
    api
      .resolveEvidence(requested, abort.signal)
      .then(async (result) => {
        if (abort.signal.aborted) return;
        setSource(result);
        const attachment = referenceAttachmentId(result);
        if (attachment) {
          const item = await api.attachment(attachment, abort.signal);
          if (!abort.signal.aborted) setSelected(item);
        }
      })
      .catch((reason) => {
        if (!abort.signal.aborted) setSourceError(reason.message);
      });
    return () => abort.abort();
  }, [requested]);
  function choose(item: EvidenceItem) {
    setSelected(item);
    setZoom(1);
    setParams({ evidence: item.id });
  }
  const excerpts =
    sections.data?.chunks.filter((row) => row.attachment_id === selected?.id) ??
    [];
  return (
    <>
      <PageHeader
        eyebrow="Original sources and provenance"
        title="Evidence Inspector"
        description="Inspect uploaded files, exact references and extracted observations. Source validity does not establish a physical cause."
        actions={
          <>
            <Link className="button button-ghost" to="/knowledge">
              Document workspaces
            </Link>
            <Button variant="secondary" onClick={list.reload}>
              <RefreshCw size={15} />
              Refresh
            </Button>
          </>
        }
      />
      {sourceError && (
        <StatePanel
          kind="error"
          title="Source reference unavailable"
          message={sourceError}
        />
      )}
      <div className="data-layout">
        <Card title="Source library">
          <div className="evidence-toolbar">
            <input
              aria-label="Search evidence"
              placeholder="Search files"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
            <select
              aria-label="Evidence modality"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All modalities</option>
              {["image", "document", "csv", "audio", "video"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
          {list.loading ? (
            <LoadingRows count={6} />
          ) : list.error ? (
            <StatePanel
              kind="error"
              title="Sources unavailable"
              message={list.error}
              action={<Button onClick={list.reload}>Retry</Button>}
            />
          ) : !list.data?.items.length ? (
            <StatePanel
              kind="empty"
              title="No matching files"
              message="Attach a file in a conversation or adjust the filters."
            />
          ) : (
            <>
              <div className="evidence-list">
                {list.data.items.map((item) => (
                  <button
                    key={item.id}
                    className={selected?.id === item.id ? "selected" : ""}
                    onClick={() => choose(item)}
                  >
                    {item.kind === "image" ? (
                      <FileImage size={18} />
                    ) : (
                      <FileText size={18} />
                    )}
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {item.kind} ·{" "}
                        {item.sizeBytes === undefined
                          ? "Size unavailable"
                          : `${item.sizeBytes.toLocaleString()} bytes`}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
              <div className="pagination">
                <Button
                  variant="ghost"
                  disabled={page <= 1}
                  onClick={() => setPage((v) => v - 1)}
                >
                  <ArrowLeft size={15} />
                  Previous
                </Button>
                <span>
                  {page} · {list.data.total} files
                </span>
                <Button
                  variant="ghost"
                  disabled={page * list.data.pageSize >= list.data.total}
                  onClick={() => setPage((v) => v + 1)}
                >
                  Next
                  <ArrowRight size={15} />
                </Button>
              </div>
            </>
          )}
        </Card>
        <div className="evidence-detail">
          {selected && (
            <>
              <Card title={selected.name}>
                <DefinitionList
                  items={[
                    { label: "Modality", value: selected.kind },
                    {
                      label: "Added",
                      value: new Date(selected.createdAt).toLocaleString(),
                    },
                    {
                      label: "Review status",
                      value: selected.quality?.status ?? "Unverified",
                    },
                  ]}
                />
                {selected.quality?.notes.map((note, index) => (
                  <p className="quality-notes" key={index}>
                    {note}
                  </p>
                ))}
                <div className="row-actions">
                  <a
                    className="button button-secondary"
                    href={`/api/v1/attachments/${encodeURIComponent(selected.id)}/content`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open original file
                  </a>
                  {selected.conversationId && (
                    <Link
                      className="button button-ghost"
                      to={`/chat/${selected.conversationId}`}
                    >
                      Open source conversation
                    </Link>
                  )}
                </div>
              </Card>
              <Card
                title="Source preview"
                action={
                  selected.kind === "image" ? (
                    <div className="zoom-controls">
                      <Button
                        variant="ghost"
                        aria-label="Zoom out"
                        onClick={() => setZoom((v) => Math.max(0.5, v - 0.25))}
                      >
                        <ZoomOut size={15} />
                      </Button>
                      <span>{Math.round(zoom * 100)}%</span>
                      <Button
                        variant="ghost"
                        aria-label="Zoom in"
                        onClick={() => setZoom((v) => Math.min(3, v + 0.25))}
                      >
                        <ZoomIn size={15} />
                      </Button>
                    </div>
                  ) : undefined
                }
              >
                <div className="media-preview">
                  {selected.kind === "image" ? (
                    <div className="image-preview">
                      <img
                        alt={selected.name}
                        src={`/api/v1/attachments/${selected.id}/content`}
                        style={{ transform: `scale(${zoom})` }}
                      />
                    </div>
                  ) : selected.kind === "audio" ? (
                    <audio
                      controls
                      preload="metadata"
                      src={`/api/v1/attachments/${selected.id}/content`}
                    />
                  ) : selected.kind === "video" ? (
                    <video
                      controls
                      preload="metadata"
                      src={`/api/v1/attachments/${selected.id}/content`}
                    />
                  ) : selected.preview?.columns?.length ? (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            {selected.preview.columns.map((column) => (
                              <th key={column}>{column}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {selected.preview.rows?.map((row, index) => (
                            <tr key={index}>
                              {row.map((value, column) => (
                                <td key={column}>{String(value ?? "")}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : sections.loading ? (
                    <LoadingRows count={3} />
                  ) : excerpts.length ? (
                    <div className="source-text">
                      {excerpts.slice(0, 30).map((row, index) => (
                        <section key={index}>
                          <strong>{row.locator}</strong>
                          <p>{row.text}</p>
                        </section>
                      ))}
                      {excerpts.length > 30 && (
                        <p>
                          Showing the first 30 extracted sections. Open the
                          original for the full source.
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="empty-copy">
                      No extracted text preview is available. Inspect the
                      original file and any extraction warnings.
                    </p>
                  )}
                </div>
              </Card>
              <Card title="File metadata and transformations">
                <details className="trace">
                  <summary>
                    Checksums, media timestamps and parser/model output
                  </summary>
                  <pre>{JSON.stringify(selected.rawMetadata, null, 2)}</pre>
                </details>
              </Card>
            </>
          )}
          {source !== null && (
            <Card title="Exact evidence reference">
              <details className="trace" open>
                <summary>
                  Source identity, locator and verification scope
                </summary>
                <pre>{JSON.stringify(source, null, 2)}</pre>
              </details>
            </Card>
          )}
          {!selected && !requested && (
            <p className="empty-copy">Select a source to inspect it.</p>
          )}
        </div>
      </div>
    </>
  );
}

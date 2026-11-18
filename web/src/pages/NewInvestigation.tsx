import {
  FileImage,
  FileSpreadsheet,
  Info,
  Paperclip,
  Send,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { CapabilityGate } from "@/components/CapabilityGate";
import { Button, Card, Field, PageHeader, StatePanel } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { api } from "@/services/api";
import { validateInvestigation } from "@/utils/validation";

export function NewInvestigation() {
  const { capabilities } = useApi();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitLock = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const validation = useMemo(
    () => validateInvestigation(question, files, capabilities?.uploads),
    [capabilities?.uploads, files, question],
  );

  function addFiles(incoming: FileList | null) {
    if (!incoming) return;
    setFiles((current) => [...current, ...Array.from(incoming)]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!validation.valid || submitLock.current) return;
    submitLock.current = true;
    const controller = new AbortController();
    request.current = controller;
    setSubmitted(true);
    setError(null);
    const form = new FormData();
    form.set("question", question.trim());
    if (context.trim()) form.set("context", context.trim());
    files.forEach((file) => form.append("evidence", file, file.name));
    try {
      const result = await api.createInvestigation(form, controller.signal);
      navigate(`/investigations/${encodeURIComponent(result.id)}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The investigation could not be created.",
      );
    } finally {
      submitLock.current = false;
      setSubmitted(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="New investigation"
        title="Tell us what went wrong"
        description="Describe the issue and attach the Sensor Data or images needed for Evidence Analysis."
      />
      <CapabilityGate
        capability="investigations"
        title="New investigations"
        unavailableTitle="Connect to SIRE to start an investigation"
      >
        <form onSubmit={submit} className="investigation-form">
          <div className="form-main">
            {error && (
              <StatePanel
                kind="error"
                title="Submission failed"
                message={error}
              />
            )}
            <Card title="Investigation brief">
              <Field
                label="Question"
                hint="Describe the asset, observed condition, timeframe, and decision you need to make."
                error={validation.questionError}
              >
                <textarea
                  rows={5}
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="What do you need to determine?"
                  maxLength={2000}
                />
              </Field>
              <div className="character-count mono">
                {question.length} / 2,000
              </div>
              <Field
                label="Operational context"
                hint="Optional. Include known operating conditions or constraints; do not paste secrets."
              >
                <textarea
                  rows={4}
                  value={context}
                  onChange={(event) => setContext(event.target.value)}
                  placeholder="Add relevant context without assuming a cause."
                  maxLength={4000}
                />
              </Field>
            </Card>
            <Card title="Evidence">
              {capabilities?.uploads.state === "available" ? (
                <>
                  <button
                    className="dropzone"
                    type="button"
                    onClick={() => inputRef.current?.click()}
                  >
                    <Paperclip size={20} />
                    <strong>Add files for investigation</strong>
                    <span>
                      {acceptedDescription(capabilities.uploads.acceptedTypes)}
                      {capabilities.uploads.maxBytes
                        ? ` · Up to ${formatBytes(capabilities.uploads.maxBytes)} per file`
                        : ""}
                    </span>
                  </button>
                  <input
                    ref={inputRef}
                    className="sr-only"
                    type="file"
                    multiple
                    accept={capabilities.uploads.acceptedTypes?.join(",")}
                    onChange={(event) => {
                      const selected = Array.from(
                        event.currentTarget.files ?? [],
                      );
                      event.currentTarget.value = "";
                      setFiles((current) => [...current, ...selected]);
                    }}
                  />
                  {files.length > 0 && (
                    <div className="file-list">
                      {files.map((file, index) => (
                        <div
                          className="file-row"
                          key={`${file.name}-${file.lastModified}`}
                        >
                          {file.type.startsWith("image/") ? (
                            <FileImage size={17} />
                          ) : (
                            <FileSpreadsheet size={17} />
                          )}
                          <span>
                            <strong>{file.name}</strong>
                            <small>
                              {formatBytes(file.size)} · Pending SIRE Backend
                              validation
                            </small>
                          </span>
                          <button
                            type="button"
                            className="icon-button"
                            aria-label={`Remove ${file.name}`}
                            onClick={() =>
                              setFiles((items) =>
                                items.filter(
                                  (_, itemIndex) => itemIndex !== index,
                                ),
                              )
                            }
                          >
                            <X size={16} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {validation.fileErrors.map((message) => (
                    <p className="field-error" key={message}>
                      {message}
                    </p>
                  ))}
                </>
              ) : (
                <StatePanel
                  kind="gated"
                  title="Evidence upload unavailable"
                  message={
                    capabilities?.uploads.reason ??
                    "The SIRE Backend has not provided file types and size limits."
                  }
                />
              )}
            </Card>
          </div>
          <aside className="guidance-column">
            <Card title="Submission check">
              <ul className="check-list">
                <li data-valid={question.trim().length >= 10}>
                  Question is specific enough to review
                </li>
                <li data-valid={validation.fileErrors.length === 0}>
                  Evidence meets file requirements
                </li>
                <li data-valid={capabilities?.qwen.state === "available"}>
                  Qwen Evidence Analysis available
                </li>
                <li
                  data-valid={capabilities?.persistence.state === "available"}
                >
                  Investigation history available
                </li>
              </ul>
            </Card>
            <div className="guidance-note">
              <Info size={17} />
              <p>
                <strong>Evidence review</strong> Qwen analysis is not a
                confirmed finding. Review Investigation Findings against linked
                evidence and stated uncertainty.
              </p>
            </div>
            <Link to="/live" className="button button-secondary">
              Open Live Conversation
            </Link>
            <Button
              type="submit"
              disabled={!validation.valid || submitted}
              title={
                submitted
                  ? "Investigation submission is in progress."
                  : !validation.valid
                    ? "Complete the investigation question and resolve file errors."
                    : undefined
              }
            >
              <Send size={16} />{" "}
              {submitted ? "Submitting…" : "Submit investigation"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => navigate("/")}>
              Cancel
            </Button>
          </aside>
        </form>
      </CapabilityGate>
    </>
  );
}

function acceptedDescription(types?: string[]) {
  return types?.length
    ? `Accepted: ${types.join(", ")}`
    : "Accepted types are provided by the SIRE Backend";
}
function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

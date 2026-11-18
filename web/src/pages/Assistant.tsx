import { Activity, CircleAlert, FileSearch, Wrench, Mic2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { Chat } from "../features/chat/Chat";
import { SireIdentity } from "../components/SireIdentity";
import { PageHeader } from "../components/ui";
import { usePreferences } from "../hooks/usePreferences";
import { api, type ProviderState } from "../lib/api";

/** Delivered conversation design backed by the existing streaming chat/voice controller. */
export function Assistant({ live = false }: { live?: boolean }) {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [composeEpoch, setComposeEpoch] = useState(
    params.get("new") ?? "conversation",
  );
  const requestedEpoch = params.get("new");
  useEffect(() => {
    if (requestedEpoch) setComposeEpoch(requestedEpoch);
  }, [requestedEpoch]);
  const { preferences } = usePreferences();
  const [providers, setProviders] = useState<ProviderState | null>(null);
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    api<ProviderState>("/providers", undefined, undefined, abort.signal)
      .then(setProviders)
      .catch((reason) => {
        if (!abort.signal.aborted) setError(reason.message);
      });
    return () => abort.abort();
  }, []);
  const current = id || null;
  useEffect(() => {
    if (current) sessionStorage.setItem("sire:active-conversation", current);
  }, [current]);
  function refresh() {
    window.dispatchEvent(new Event("sire:conversations-changed"));
  }
  function route(path: string) {
    const next = live ? path.replace(/^\/chat/, "/live") : path;
    navigate(next);
  }
  const welcome = (
    <div className="conversation-empty">
      <SireIdentity />
      <h2>{live ? "Talk to SIRE" : "How can SIRE help you?"}</h2>
      <p>
        {live
          ? "Start the microphone below. Your final utterances are sent automatically, and SIRE speaks its replies."
          : "Let's understand what's happening with your equipment."}
      </p>
      {!live && (
        <div className="conversation-starters">
          <Link to="/investigations/new" className="starter-card">
            <Activity size={19} />
            <span>
              <strong>Analyze sensor data</strong>
              <small>Review your actual measurements.</small>
            </span>
          </Link>
          <Link to="/investigations/new" className="starter-card">
            <CircleAlert size={19} />
            <span>
              <strong>Investigate a fault</strong>
              <small>Compare evidence and possible causes.</small>
            </span>
          </Link>
          <Link to="/rul" className="starter-card">
            <Wrench size={19} />
            <span>
              <strong>Estimate remaining useful life</strong>
              <small>Explore C-MAPSS predictions.</small>
            </span>
          </Link>
          <Link to="/evidence" className="starter-card">
            <FileSearch size={19} />
            <span>
              <strong>Review evidence</strong>
              <small>Inspect the original sources.</small>
            </span>
          </Link>
        </div>
      )}
    </div>
  );
  return (
    <div className={`assistant-page ${live ? "live-page" : ""}`}>
      <PageHeader
        eyebrow={live ? "Local voice conversation" : "Industrial Intelligence"}
        title={live ? "Talk to SIRE" : "SIRE Assistant"}
        description={
          live
            ? "Continuous capture, final local transcription and automatic local speech. Use Interrupt and speak to take a turn."
            : "Ask a question, attach evidence or start an investigation."
        }
        actions={
          <Link
            className="button button-secondary"
            to={
              live
                ? current
                  ? `/chat/${current}`
                  : "/"
                : current
                  ? `/live/${current}`
                  : "/live"
            }
          >
            {live ? (
              "Switch to text"
            ) : (
              <>
                <Mic2 size={16} />
                Live conversation
              </>
            )}
          </Link>
        }
      />
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="assistant-model">
        <label>
          Conversation model{" "}
          <select
            aria-label="Conversation model"
            value={model || providers?.configured_text || ""}
            disabled={busy || !providers?.models.length}
            onChange={(e) => setModel(e.target.value)}
          >
            {!providers?.models.length && (
              <option value="">
                {error
                  ? "Backend unavailable"
                  : providers
                    ? "No local model available"
                    : "Checking local model…"}
              </option>
            )}
            {providers?.configured_text &&
              !providers.models.some(
                (item) => item.name === providers.configured_text,
              ) && (
                <option value={providers.configured_text}>
                  Configured model unavailable
                </option>
              )}
            {providers?.models
              .filter(
                (item) =>
                  !item.capabilities?.includes("thinking") ||
                  item.name === providers.configured_text,
              )
              .map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
          </select>
        </label>
        <span>{busy ? "Working…" : "Local inference"}</span>
      </div>
      <Chat
        key={composeEpoch}
        id={current}
        model={model || providers?.configured_text || ""}
        predictionId={params.get("prediction")}
        navigate={route}
        refresh={refresh}
        setBusy={setBusy}
        welcome={welcome}
        liveVoice={live}
        speechEnabled={preferences.audioEnabled}
        audioPreferences={preferences}
      />
    </div>
  );
}

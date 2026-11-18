import { Activity, Clock, RefreshCw, Server } from "lucide-react";
import {
  Button,
  Card,
  CapabilityBadge,
  LoadingRows,
  PageHeader,
  StatePanel,
  StatusDot,
} from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useRemote } from "@/hooks/useRemote";
import { api, apiBaseUrl } from "@/services/api";

export function SystemStatus() {
  const capabilitiesState = useApi();
  const status = useRemote(
    (signal) => api.status(signal),
    [capabilitiesState.capabilities?.checkedAt],
  );
  function refresh() {
    capabilitiesState.refresh();
    status.reload();
  }
  const gpuStatus = status.data?.services.find((service) =>
    /gpu|cuda/i.test(service.name),
  );
  const localInference = status.data?.services.find((service) =>
    /local inference/i.test(service.name),
  );
  return (
    <>
      <PageHeader
        eyebrow="Service Diagnostics"
        title="System Status"
        description="Review SIRE Backend, Orchestrator and analysis service availability."
        actions={
          <Button variant="secondary" onClick={refresh}>
            <RefreshCw size={15} /> Refresh checks
          </Button>
        }
      />
      <div className="status-summary">
        <Card>
          <div className="status-tile">
            <Server size={19} />
            <span>
              <small>SIRE Backend</small>
              <strong>
                {capabilitiesState.capabilities ? "Connected" : "Not connected"}
              </strong>
            </span>
            <StatusDot
              state={capabilitiesState.capabilities ? "good" : "bad"}
            />
          </div>
        </Card>
        <Card>
          <div className="status-tile">
            <Activity size={19} />
            <span>
              <small>Service version</small>
              <strong>
                {capabilitiesState.capabilities
                  ? `v${capabilitiesState.capabilities.apiVersion}`
                  : "Unavailable"}
              </strong>
            </span>
            <StatusDot
              state={capabilitiesState.capabilities ? "good" : "unknown"}
            />
          </div>
        </Card>
        <Card>
          <div className="status-tile">
            <Clock size={19} />
            <span>
              <small>Last status check</small>
              <strong>
                {capabilitiesState.capabilities
                  ? new Date(
                      capabilitiesState.capabilities.checkedAt,
                    ).toLocaleTimeString()
                  : "Never"}
              </strong>
            </span>
            <StatusDot
              state={capabilitiesState.capabilities ? "good" : "unknown"}
            />
          </div>
        </Card>
      </div>
      {(gpuStatus || localInference) && (
        <div className="status-summary">
          {gpuStatus && <VerifiedStatusTile label="GPU" service={gpuStatus} />}
          {localInference && (
            <VerifiedStatusTile
              label="Local inference"
              service={localInference}
            />
          )}
        </div>
      )}
      <Card title="Investigation Services">
        {capabilitiesState.loading ? (
          <LoadingRows count={5} />
        ) : capabilitiesState.error ? (
          <StatePanel
            kind="error"
            title="Service check failed"
            message={capabilitiesState.error}
          />
        ) : (
          capabilitiesState.capabilities && (
            <div className="capability-grid">
              {(
                [
                  "investigations",
                  "persistence",
                  "uploads",
                  "qwen",
                  "kokoro",
                  "voiceInput",
                  "cmapss",
                ] as const
              ).map((key) => (
                <div key={key}>
                  <span>{serviceLabel(key)}</span>
                  <CapabilityBadge
                    state={capabilitiesState.capabilities![key].state}
                  />
                  <small>
                    {capabilitiesState.capabilities![key].reason ??
                      capabilitiesState.capabilities![key].model ??
                      "Available"}
                  </small>
                </div>
              ))}
            </div>
          )
        )}
      </Card>
      <Card title="Voice and investigation contracts">
        <p>
          Live voice uses the local PCM WebSocket session, final Whisper
          utterances and automatically queued Kokoro speech. Start capture
          explicitly on the Live Conversation page. Physical microphone, speaker
          and interruption behavior still require device testing.
        </p>
        <p>
          Source-scoped saved cases, prediction inventory, operational traces
          and explicit scenario what-if are connected to the existing SIRE
          interfaces.
        </p>
      </Card>
      <Card title="Service health">
        {status.loading ? (
          <LoadingRows count={5} />
        ) : status.error ? (
          <StatePanel
            kind="error"
            title="Diagnostics unavailable"
            message={status.error}
          />
        ) : !status.data?.services.length ? (
          <StatePanel
            kind="empty"
            title="No service diagnostics"
            message="No service status information is available."
          />
        ) : (
          <div className="service-list">
            {status.data.services.map((service) => (
              <div className="service-row detailed" key={service.name}>
                <StatusDot
                  state={
                    service.state === "operational"
                      ? "good"
                      : service.state === "degraded"
                        ? "warn"
                        : service.state === "offline"
                          ? "bad"
                          : "unknown"
                  }
                />
                <span>
                  <strong>{service.name}</strong>
                  <small>
                    {service.message ??
                      ([service.model, service.version]
                        .filter(Boolean)
                        .join(" · ") ||
                        "No detail supplied")}
                  </small>
                </span>
                <div>
                  {service.latencyMs !== undefined && (
                    <span className="mono">{service.latencyMs} ms</span>
                  )}
                  <span
                    className={`status-label status-label-${service.state}`}
                  >
                    {service.state}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
function VerifiedStatusTile({
  label,
  service,
}: {
  label: string;
  service: { state: string; message?: string };
}) {
  return (
    <Card>
      <div className="status-tile">
        <Activity size={19} />
        <span>
          <small>{label}</small>
          <strong>{service.message ?? service.state}</strong>
        </span>
        <StatusDot
          state={
            service.state === "operational"
              ? "good"
              : service.state === "degraded"
                ? "warn"
                : "bad"
          }
        />
      </div>
    </Card>
  );
}
function serviceLabel(value: string) {
  return {
    investigations: "Investigation Engine",
    persistence: "Investigation History",
    uploads: "Evidence Analysis",
    qwen: "Qwen",
    kokoro: "Kokoro",
    voiceInput: "Speech Input",
    cmapss: "CMAPSS",
  }[value];
}

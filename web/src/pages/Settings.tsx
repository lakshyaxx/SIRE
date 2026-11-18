import {
  Activity,
  Headphones,
  Info,
  Mic2,
  Monitor,
  PanelLeft,
  RefreshCw,
  Volume2,
  Waves,
} from "lucide-react";
import { Link } from "react-router";
import {
  Button,
  Card,
  PageHeader,
  Select,
  StatePanel,
  StatusDot,
  Toggle,
} from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { usePreferences } from "@/hooks/usePreferences";
import { useMediaDevices } from "@/hooks/useMediaDevices";

export function Settings() {
  const { preferences, update } = usePreferences();
  const devices = useMediaDevices();
  const backend = useApi();
  const connectionLabel = backend.capabilities
    ? "Connected"
    : backend.loading
      ? "Connecting"
      : backend.error
        ? "Disconnected"
        : "Unavailable";
  const connectionState = backend.capabilities
    ? "good"
    : backend.loading
      ? "warn"
      : "bad";

  return (
    <>
      <PageHeader
        eyebrow="Application Preferences"
        title="Settings"
        description="Manage your display, navigation and audio preferences."
      />
      <div className="settings-layout">
        <div className="settings-column">
          <Card title="Interface Preferences">
            <SettingRow
              icon={<Waves size={18} />}
              label="Density"
              description="Adjust control and row spacing."
            >
              <Select
                className="settings-select"
                value={preferences.density}
                onChange={(value) =>
                  update("density", value as typeof preferences.density)
                }
                label="Interface density"
                options={[
                  { value: "comfortable", label: "Comfortable" },
                  { value: "compact", label: "Compact" },
                ]}
              />
            </SettingRow>
            <SettingRow
              icon={<PanelLeft size={18} />}
              label="Sidebar"
              description="Keep primary navigation collapsed."
            >
              <Toggle
                checked={preferences.sidebarCollapsed}
                onChange={(value) => update("sidebarCollapsed", value)}
                label="Collapse sidebar"
              />
            </SettingRow>
            <SettingRow
              icon={<Monitor size={18} />}
              label="Reduced motion"
              description="Minimize non-essential interface movement."
            >
              <Toggle
                checked={preferences.reduceMotion}
                onChange={(value) => update("reduceMotion", value)}
                label="Reduce motion"
              />
            </SettingRow>
          </Card>

          <Card title="Audio Controls">
            <SettingRow
              icon={<Headphones size={18} />}
              label="Speech playback"
              description="Show audio controls when Kokoro is available."
            >
              <Toggle
                checked={preferences.audioEnabled}
                onChange={(value) => update("audioEnabled", value)}
                label="Enable audio"
              />
            </SettingRow>
            <SettingRow
              icon={<Volume2 size={18} />}
              label="Playback volume"
              description={`${Math.round(preferences.playbackVolume * 100)} percent`}
            >
              <div className="range-control">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={preferences.playbackVolume}
                  onChange={(event) =>
                    update("playbackVolume", Number(event.target.value))
                  }
                  aria-label="Playback volume"
                />
                <output>{Math.round(preferences.playbackVolume * 100)}%</output>
              </div>
            </SettingRow>
            <p className="settings-note">
              Speech controls appear only when the SIRE Backend reports the
              required service.
            </p>
          </Card>
        </div>

        <div className="settings-column">
          <Card title="Audio Devices">
            <SettingRow
              icon={<Mic2 size={18} />}
              label="Microphone"
              description="Select the device used for local voice sessions."
            >
              <Select
                className="settings-select"
                value={preferences.microphoneId}
                onChange={(value) => update("microphoneId", value)}
                label="Microphone"
                disabled={!devices.inputs.length}
                title={
                  !devices.inputs.length
                    ? "No microphone is available."
                    : undefined
                }
                options={[
                  { value: "", label: "System default" },
                  ...devices.inputs.map((device, index) => ({
                    value: device.deviceId,
                    label: device.label || `Microphone ${index + 1}`,
                  })),
                ]}
              />
            </SettingRow>
            <SettingRow
              icon={<Headphones size={18} />}
              label="Speaker"
              description="Select the playback device where supported."
            >
              <Select
                className="settings-select"
                value={preferences.speakerId}
                onChange={(value) => update("speakerId", value)}
                label="Speaker"
                disabled={!devices.outputs.length}
                title={
                  !devices.outputs.length
                    ? "No selectable speaker is available."
                    : undefined
                }
                options={[
                  { value: "", label: "System default" },
                  ...devices.outputs.map((device, index) => ({
                    value: device.deviceId,
                    label: device.label || `Speaker ${index + 1}`,
                  })),
                ]}
              />
            </SettingRow>
            <div className="device-readiness">
              <Readiness
                label="Microphone permission"
                value={devices.permission}
                state={
                  devices.permission === "granted"
                    ? "good"
                    : devices.permission === "requesting"
                      ? "warn"
                      : "unknown"
                }
              />
              <Readiness
                label="Speech recognition"
                value={backend.capabilities?.voiceInput.state ?? "unavailable"}
                state={
                  backend.capabilities?.voiceInput.state === "available"
                    ? "good"
                    : "unknown"
                }
              />
              <Readiness
                label="Kokoro speech"
                value={backend.capabilities?.kokoro.state ?? "unavailable"}
                state={
                  backend.capabilities?.kokoro.state === "available"
                    ? "good"
                    : "unknown"
                }
              />
            </div>
            <div className="device-test">
              <div
                className="microphone-meter"
                aria-label="Microphone input level"
              >
                <span style={{ width: `${devices.level * 100}%` }} />
              </div>
              <Button
                variant="secondary"
                disabled={
                  devices.testing || devices.permission === "unavailable"
                }
                title={
                  devices.permission === "unavailable"
                    ? "Microphone access is unavailable in this browser."
                    : devices.testing
                      ? "Microphone test in progress."
                      : undefined
                }
                onClick={() =>
                  void devices.testMicrophone(preferences.microphoneId)
                }
              >
                {devices.testing ? "Testing microphone…" : "Test microphone"}
              </Button>
              <Button
                variant="secondary"
                disabled
                title="No approved speaker test audio is available."
              >
                Test speaker
              </Button>
            </div>
            {devices.error && (
              <StatePanel
                kind="error"
                title="Audio device unavailable"
                message={devices.error}
              />
            )}
          </Card>

          <Card title="Connection & Diagnostics">
            <div className="connection-status-row">
              <StatusDot state={connectionState} />
              <div>
                <strong>SIRE Backend</strong>
                <small>{connectionLabel}</small>
              </div>
            </div>
            <p className="settings-note">
              Investigation, evidence and analysis services depend on a verified
              connection.
            </p>
            <div className="settings-actions">
              <Button
                variant="secondary"
                onClick={backend.refresh}
                disabled={backend.loading}
              >
                <RefreshCw size={15} />{" "}
                {backend.loading ? "Checking…" : "Check connection"}
              </Button>
              <Link to="/status" className="button button-secondary">
                <Activity size={15} /> System Diagnostics
              </Link>
            </div>
          </Card>

          <Card title="About SIRE">
            <div className="about-block">
              <Info size={20} />
              <div>
                <strong>Industrial investigation and diagnostics</strong>
                <p>
                  SIRE combines Investigation Findings, Evidence Analysis and
                  Predictive Analysis. Findings and predictions require
                  qualified engineering review.
                </p>
                <span className="mono">SIRE v1</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
function SettingRow({
  icon,
  label,
  description,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="setting-row">
      <div className="setting-icon">{icon}</div>
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      {children}
    </div>
  );
}

function Readiness({
  label,
  value,
  state,
}: {
  label: string;
  value: string;
  state: "good" | "warn" | "bad" | "unknown";
}) {
  return (
    <div>
      <StatusDot state={state} />
      <span>{label}</span>
      <strong>{value.replace("-", " ")}</strong>
    </div>
  );
}

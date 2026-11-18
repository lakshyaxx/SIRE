import type { ReactNode } from "react";
import { useApi } from "@/hooks/useApi";
import type { Capabilities } from "@/types/api";
import { StatePanel } from "./ui";

type CapabilityKey = keyof Pick<
  Capabilities,
  | "investigations"
  | "persistence"
  | "uploads"
  | "qwen"
  | "kokoro"
  | "voiceInput"
  | "cmapss"
>;

export function CapabilityGate({
  capability,
  children,
  title,
  unavailableTitle,
}: {
  capability: CapabilityKey;
  children: ReactNode;
  title: string;
  unavailableTitle?: string;
}) {
  const { capabilities, loading, error } = useApi();
  if (loading)
    return (
      <StatePanel
        kind="loading"
        title="Checking service"
        message={`Checking ${title} availability.`}
      />
    );
  if (!capabilities) {
    return (
      <StatePanel
        kind="gated"
        title={unavailableTitle ?? `${title} unavailable`}
        message={error ?? "The SIRE Backend has not confirmed this service."}
      />
    );
  }
  const state = capabilities[capability];
  if (state.state !== "available") {
    return (
      <StatePanel
        kind="gated"
        title={unavailableTitle ?? `${title} unavailable`}
        message={
          state.reason ??
          "The SIRE Backend has not made this service available."
        }
      />
    );
  }
  return <>{children}</>;
}

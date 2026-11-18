import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Preferences = {
  density: "comfortable" | "compact";
  sidebarCollapsed: boolean;
  reduceMotion: boolean;
  audioEnabled: boolean;
  microphoneId: string;
  speakerId: string;
  playbackVolume: number;
};

const defaults: Preferences = {
  density: "comfortable",
  sidebarCollapsed: false,
  reduceMotion: false,
  audioEnabled: true,
  microphoneId: "",
  speakerId: "",
  playbackVolume: 0.8,
};

type PreferencesContextValue = {
  preferences: Preferences;
  update: <K extends keyof Preferences>(key: K, value: Preferences[K]) => void;
};
const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function normalizePreferences(stored: unknown): Preferences {
  if (!stored || typeof stored !== "object" || Array.isArray(stored))
    return defaults;
  const current = stored as Record<string, unknown>;
  return {
    density: current.density === "compact" ? "compact" : "comfortable",
    sidebarCollapsed:
      typeof current.sidebarCollapsed === "boolean"
        ? current.sidebarCollapsed
        : defaults.sidebarCollapsed,
    reduceMotion:
      typeof current.reduceMotion === "boolean"
        ? current.reduceMotion
        : defaults.reduceMotion,
    audioEnabled:
      typeof current.audioEnabled === "boolean"
        ? current.audioEnabled
        : defaults.audioEnabled,
    microphoneId:
      typeof current.microphoneId === "string"
        ? current.microphoneId
        : defaults.microphoneId,
    speakerId:
      typeof current.speakerId === "string"
        ? current.speakerId
        : defaults.speakerId,
    playbackVolume:
      typeof current.playbackVolume === "number" &&
      current.playbackVolume >= 0 &&
      current.playbackVolume <= 1
        ? current.playbackVolume
        : defaults.playbackVolume,
  };
}

function readPreferences(): Preferences {
  try {
    return normalizePreferences(
      JSON.parse(localStorage.getItem("sire:preferences") ?? "{}"),
    );
  } catch {
    return defaults;
  }
}

export function PreferencesProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [preferences, setPreferences] = useState<Preferences>(readPreferences);
  useEffect(() => {
    localStorage.setItem("sire:preferences", JSON.stringify(preferences));
    delete document.documentElement.dataset.theme;
    document.documentElement.dataset.density = preferences.density;
    document.documentElement.classList.toggle(
      "reduce-motion",
      preferences.reduceMotion,
    );
  }, [preferences]);
  const update = <K extends keyof Preferences>(key: K, value: Preferences[K]) =>
    setPreferences((current) => ({ ...current, [key]: value }));
  const value = useMemo(() => ({ preferences, update }), [preferences]);
  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context)
    throw new Error("usePreferences must be used inside PreferencesProvider");
  return context;
}

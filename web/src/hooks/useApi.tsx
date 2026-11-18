import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, apiBaseUrl } from "@/services/api";
import type { Capabilities } from "@/types/api";

type ApiContextValue = {
  capabilities: Capabilities | null;
  loading: boolean;
  error: string | null;
  configured: boolean;
  refresh: () => void;
};

const ApiContext = createContext<ApiContextValue | null>(null);

export function ApiProvider({ children }: { children: React.ReactNode }) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(Boolean(apiBaseUrl));
  const [error, setError] = useState<string | null>(
    apiBaseUrl
      ? null
      : "Connect to the SIRE backend to access investigation services.",
  );
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    setLoading(true);
    api
      .capabilities(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setCapabilities(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setCapabilities(null);
        setError(
          reason instanceof Error
            ? reason.message
            : "Investigation service check failed.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  const refresh = useCallback(() => {
    setRevision((value) => value + 1);
  }, []);
  const value = useMemo(
    () => ({
      capabilities,
      loading,
      error,
      configured: Boolean(apiBaseUrl),
      refresh,
    }),
    [capabilities, error, loading, refresh],
  );
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
}

export function useApi() {
  const context = useContext(ApiContext);
  if (!context) throw new Error("useApi must be used inside ApiProvider");
  return context;
}

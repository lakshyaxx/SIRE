import { useCallback, useEffect, useRef, useState } from "react";

export function useRemote<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  dependencies: unknown[],
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const scope = useRef(dependencies);
  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const changed =
      dependencies.length !== scope.current.length ||
      dependencies.some((value, index) => value !== scope.current[index]);
    scope.current = dependencies;
    setLoading(changed || data === null);
    if (changed) setData(null);
    setError(null);
    loader(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(reason instanceof Error ? reason.message : "Request failed.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // Dependencies are deliberately controlled by callers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, revision]);
  return { data, loading, error, reload };
}

import { Models } from "../features/models/Models";
import { useRemote } from "../hooks/useRemote";
import { api } from "../lib/api";
import { Card, PageHeader, StatePanel } from "../components/ui";
export function ModelInventory() {
  const providers = useRemote(
    (signal) =>
      api<{
        providers: {
          id: string;
          model: string;
          provider: string;
          availability: string;
          health: string;
          capabilities: string[];
        }[];
      }>("/providers/registry", undefined, undefined, signal),
    [],
  );
  return (
    <>
      <PageHeader
        title="Model inventory"
        description="Actual installed specialist configuration and preserved NASA research catalog."
      />
      {providers.error && (
        <StatePanel
          kind="error"
          title="Providers unavailable"
          message={providers.error}
        />
      )}
      <Card title="Specialists">
        <div className="provider-grid">
          {providers.data?.providers
            .filter((row) => row.provider !== "preserved_native")
            .map((row) => (
              <article className="provider-card" key={row.id}>
                <strong>{row.model}</strong>
                <span className="status-label">
                  {row.availability.replaceAll("_", " ")}
                </span>
                <p>{row.health}</p>
                <small>{row.capabilities.join(" · ")}</small>
              </article>
            ))}
        </div>
      </Card>
      <div className="integrated-feature">
        <Models />
      </div>
    </>
  );
}

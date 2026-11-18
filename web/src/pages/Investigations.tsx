import {
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  Search,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import {
  Button,
  Card,
  LoadingRows,
  PageHeader,
  StatePanel,
} from "../components/ui";
import { useRemote } from "../hooks/useRemote";
import { api } from "../services/api";

/** Real saved general cases and durable job states; conversations remain in the sidebar. */
export function Investigations() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const result = useRemote(
    (signal) =>
      api.investigations(
        new URLSearchParams({
          query,
          status,
          page: String(page),
          pageSize: "15",
        }),
        signal,
      ),
    [query, status, page],
  );
  return (
    <>
      <PageHeader
        eyebrow="Saved evidence trails"
        title="Case History"
        description="Reopen actual investigations, findings and their source records."
        actions={
          <>
            <Button variant="secondary" onClick={result.reload}>
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Link className="button button-primary" to="/investigations/new">
              New investigation
            </Link>
          </>
        }
      />
      <Card>
        <div className="evidence-toolbar">
          <Search size={17} />
          <input
            aria-label="Search saved investigations"
            placeholder="Search investigations"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
          <select
            aria-label="Investigation status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {[
              "queued",
              "running",
              "complete",
              "partial",
              "error",
              "cancelled",
              "interrupted",
            ].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </div>
        {result.loading ? (
          <LoadingRows count={5} />
        ) : result.error ? (
          <StatePanel
            kind="error"
            title="History unavailable"
            message={result.error}
            action={<Button onClick={result.reload}>Retry</Button>}
          />
        ) : !result.data?.items.length ? (
          <StatePanel
            kind="empty"
            title="No matching investigations"
            message="Start an investigation or adjust the filters."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Investigation</th>
                    <th>Actual status</th>
                    <th>Sources</th>
                    <th>Updated</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.title}</strong>
                      </td>
                      <td>
                        <span
                          className={`status-label status-label-${item.status}`}
                        >
                          {item.status}
                        </span>
                      </td>
                      <td>{item.evidenceCount}</td>
                      <td>{new Date(item.updatedAt).toLocaleString()}</td>
                      <td>
                        <Link
                          className="icon-button"
                          aria-label={`Open ${item.title}`}
                          to={`/investigations/${encodeURIComponent(item.id)}`}
                        >
                          <ExternalLink size={17} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => setPage((v) => v - 1)}
              >
                <ArrowLeft size={15} />
                Previous
              </Button>
              <span>
                Page {page} · {result.data.total} saved records
              </span>
              <Button
                variant="secondary"
                disabled={page * result.data.pageSize >= result.data.total}
                onClick={() => setPage((v) => v + 1)}
              >
                Next
                <ArrowRight size={15} />
              </Button>
            </div>
          </>
        )}
      </Card>
      <p className="context-link">
        <Link to="/engineer">
          Open scenario replay, prior-case comparisons and explicit what-if
          simulations →
        </Link>
      </p>
    </>
  );
}

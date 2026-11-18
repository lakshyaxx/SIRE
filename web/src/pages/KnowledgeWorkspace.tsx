import { Link } from "react-router";
import { Knowledge } from "../features/knowledge/Knowledge";
import { useRemote } from "../hooks/useRemote";
import { api, type Conversation } from "../lib/api";
import { StatePanel } from "../components/ui";

/** Keep the existing complete document ingestion and passage browser reachable. */
export function KnowledgeWorkspace() {
  const conversations = useRemote(
    (signal) =>
      api<{ conversations: Conversation[] }>(
        "/conversations",
        undefined,
        undefined,
        signal,
      ),
    [],
  );
  function refresh() {
    conversations.reload();
    window.dispatchEvent(new Event("sire:conversations-changed"));
  }
  if (conversations.loading)
    return <p role="status">Loading document workspaces…</p>;
  if (conversations.error)
    return (
      <StatePanel
        kind="error"
        title="Document workspaces unavailable"
        message={conversations.error}
      />
    );
  return (
    <div className="integrated-feature">
      <p>
        <Link to="/evidence">
          Inspect all original files and multimodal evidence →
        </Link>
      </p>
      <Knowledge
        conversations={conversations.data?.conversations ?? []}
        refresh={refresh}
      />
    </div>
  );
}

import {
  Activity,
  AudioLines,
  BrainCircuit,
  ChevronLeft,
  Database,
  FileSearch,
  History,
  Home,
  Menu,
  MessageCircle,
  MessageSquarePlus,
  PanelLeftClose,
  Plus,
  Search,
  Settings,
  X,
  Pencil,
  Trash2,
  Network,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useApi } from "@/hooks/useApi";
import { usePreferences } from "@/hooks/usePreferences";
import { StatusDot } from "./ui";
import { SireBrand } from "./SireBrand";
import { api, type Conversation } from "../lib/api";

const navigation = [
  { to: "/", label: "SIRE Assistant", icon: Home, end: true },
  { to: "/live", label: "Live Conversation", icon: MessageCircle },
  {
    to: "/investigations/new",
    label: "Investigation Workspace",
    icon: FileSearch,
  },
  { to: "/evidence", label: "Evidence Inspector", icon: Database },
  { to: "/rul", label: "RUL Prediction Center", icon: BrainCircuit },
  { to: "/cases", label: "Case History", icon: History },
  { to: "/engineer", label: "Scenario & What-if", icon: Network },
];

export function AppShell() {
  const { capabilities, configured, error } = useApi();
  const { preferences, update } = usePreferences();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyError, setHistoryError] = useState("");
  useEffect(() => {
    let abort: AbortController | null = null;
    function refresh() {
      abort?.abort();
      abort = new AbortController();
      const signal = abort.signal;
      api<{ conversations: Conversation[] }>(
        "/conversations",
        undefined,
        undefined,
        signal,
      )
        .then((data) => {
          if (!signal.aborted) {
            setConversations(data.conversations);
            setHistoryError("");
          }
        })
        .catch((reason) => {
          if (!signal.aborted) setHistoryError(reason.message);
        });
    }
    refresh();
    window.addEventListener("sire:conversations-changed", refresh);
    return () => {
      abort?.abort();
      window.removeEventListener("sire:conversations-changed", refresh);
    };
  }, []);
  async function rename(item: Conversation) {
    const title = prompt("Rename conversation", item.title);
    if (!title?.trim()) return;
    try {
      await api(
        `/conversations/${encodeURIComponent(item.id)}`,
        { title: title.trim() },
        "PATCH",
      );
      window.dispatchEvent(new Event("sire:conversations-changed"));
    } catch (reason) {
      setHistoryError((reason as Error).message);
    }
  }
  async function remove(item: Conversation) {
    if (
      !confirm(
        `Delete “${item.title}” and its attachments? This cannot be undone in the app.`,
      )
    )
      return;
    try {
      await api(
        `/conversations/${encodeURIComponent(item.id)}?confirm=true`,
        undefined,
        "DELETE",
      );
      navigate("/");
      window.dispatchEvent(new Event("sire:conversations-changed"));
    } catch (reason) {
      setHistoryError((reason as Error).message);
    }
  }
  const location = useLocation();
  const navigate = useNavigate();
  const collapsed = preferences.sidebarCollapsed;
  const connectionState = capabilities
    ? "good"
    : configured && !error
      ? "warn"
      : "bad";

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside
        className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}
        aria-label="Primary navigation"
      >
        <div className="brand">
          <SireBrand
            collapsed={collapsed}
            onNavigate={() => setMobileOpen(false)}
          />
          <button
            className="icon-button mobile-close"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>
        <div className="sidebar-quick-actions">
          <button
            className="nav-item"
            onClick={() => {
              navigate(`/?new=${Date.now()}`);
              setMobileOpen(false);
            }}
            title={collapsed ? "New conversation" : undefined}
          >
            <MessageSquarePlus size={18} />
            <span>New conversation</span>
          </button>
          <NavLink
            to="/investigations/new"
            className="nav-item"
            onClick={() => setMobileOpen(false)}
            title={collapsed ? "New investigation" : undefined}
          >
            <Plus size={18} />
            <span>New investigation</span>
          </NavLink>
        </div>
        <nav>
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                isActive ? "nav-item active" : "nav-item"
              }
              title={collapsed ? label : undefined}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        {!collapsed && (
          <section
            className="conversation-history"
            aria-label="Saved conversations"
          >
            <div className="history-heading">Conversations</div>
            {historyError && (
              <p role="alert" className="error">
                {historyError}
              </p>
            )}
            {!historyError && !conversations.length && (
              <p className="empty-copy">No conversations yet.</p>
            )}
            {conversations.map((item) => (
              <div className="conversation-history-row" key={item.id}>
                <NavLink
                  to={`/chat/${item.id}`}
                  onClick={() => setMobileOpen(false)}
                  title={item.title}
                >
                  {item.title}
                </NavLink>
                <button
                  className="icon-button"
                  aria-label={`Rename ${item.title}`}
                  onClick={() => void rename(item)}
                >
                  <Pencil size={13} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`Delete ${item.title}`}
                  onClick={() => void remove(item)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </section>
        )}
        <div className="sidebar-footer">
          <NavLink
            to="/models"
            aria-label="Model inventory"
            className="nav-item"
          >
            <BrainCircuit size={18} />
            <span>Model inventory</span>
          </NavLink>
          <NavLink
            to="/settings"
            aria-label="Settings"
            className={({ isActive }) =>
              isActive ? "nav-item active" : "nav-item"
            }
          >
            <Settings size={18} />
            <span>Settings</span>
          </NavLink>
          <NavLink
            to="/status"
            aria-label="System Diagnostics"
            className={({ isActive }) =>
              isActive ? "nav-item active" : "nav-item"
            }
          >
            <Activity size={18} />
            <span>System Diagnostics</span>
          </NavLink>
          {!collapsed && (
            <div className="connection-mini">
              <StatusDot state={connectionState} />
              <div>
                <span>
                  {capabilities
                    ? "Connected"
                    : configured && !error
                      ? "Connecting"
                      : "Disconnected"}
                </span>
                <small>
                  {capabilities
                    ? "SIRE Backend ready"
                    : configured
                      ? "Checking services"
                      : "Service unavailable"}
                </small>
              </div>
            </div>
          )}
          <button
            className="collapse-button"
            onClick={() => update("sidebarCollapsed", !collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <Menu size={18} /> : <PanelLeftClose size={18} />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>
      {mobileOpen && (
        <button
          className="scrim"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <div className="main-column">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>
          <div className="breadcrumbs">
            <ChevronLeft size={14} />
            <span>Operations</span>
            <strong>{pageName(location.pathname)}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className="icon-button"
              aria-label="Search investigations"
              onClick={() => navigate("/cases")}
            >
              <Search size={18} />
            </button>
            <div className="model-state" title="Kokoro speech service status">
              <AudioLines size={15} />
              <span>
                {capabilities?.kokoro.state === "available"
                  ? "Kokoro ready"
                  : "Speech unavailable"}
              </span>
            </div>
          </div>
        </header>
        <main
          id="main-content"
          className={`content ${location.pathname === "/" || location.pathname.startsWith("/chat") || location.pathname.startsWith("/live") ? "assistant-content" : ""}`}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function pageName(path: string) {
  if (path === "/") return "SIRE Assistant";
  if (path === "/live") return "Live Conversation";
  if (path === "/investigations/new") return "New investigation";
  if (path.startsWith("/investigations/")) return "Investigation Workspace";
  if (path === "/settings") return "Settings";
  if (path === "/status") return "System Diagnostics";
  return (
    navigation.find((item) => item.to === path)?.label ??
    (path === "/settings" ? "Settings" : "SIRE")
  );
}

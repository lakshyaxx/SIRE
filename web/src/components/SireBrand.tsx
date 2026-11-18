import { Link } from "react-router";

/** One local vector source for every SIRE symbol, including the favicon. */
export function CircuitS({ className = "" }: { className?: string }) {
  return (
    <img
      className={`circuit-s ${className}`}
      src="/brand/circuit-s.svg"
      width="48"
      height="48"
      alt=""
      aria-hidden="true"
    />
  );
}

export function SireWordmark() {
  return (
    <img
      className="sire-wordmark"
      src="/brand/sire-wordmark.svg"
      width="116"
      height="28"
      alt=""
      aria-hidden="true"
    />
  );
}

export function SireBrand({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      className="brand-link"
      to="/"
      onClick={onNavigate}
      aria-label="SIRE Industrial Intelligence — Assistant homepage"
      title={collapsed ? "SIRE Assistant" : undefined}
    >
      <CircuitS />
      {!collapsed && (
        <div className="brand-copy">
          <SireWordmark />
          <span>Industrial Intelligence</span>
        </div>
      )}
    </Link>
  );
}

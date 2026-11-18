import { CircuitS } from "./SireBrand";

export function SireIdentity({
  compact = false,
  thinking = false,
}: {
  compact?: boolean;
  thinking?: boolean;
}) {
  return (
    <span
      className={`sire-identity ${compact ? "sire-identity-compact" : ""} ${thinking ? "is-thinking" : ""}`}
      aria-hidden="true"
    >
      <CircuitS />
    </span>
  );
}

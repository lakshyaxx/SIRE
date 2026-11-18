import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { SireIdentity } from "./SireIdentity";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  );
}

export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button className={`button button-${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}

export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export function Select({
  value,
  options,
  onChange,
  label,
  disabled = false,
  title,
  className = "",
}: {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  label: string;
  disabled?: boolean;
  title?: string;
  className?: string;
}) {
  const id = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const selectedIndex = Math.max(
    0,
    options.findIndex((option) => option.value === value),
  );
  const [activeIndex, setActiveIndex] = useState(selectedIndex);

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  useEffect(() => {
    if (open) setActiveIndex(selectedIndex);
  }, [open, selectedIndex]);

  function move(direction: 1 | -1) {
    let next = activeIndex;
    for (let count = 0; count < options.length; count += 1) {
      next = (next + direction + options.length) % options.length;
      if (!options[next]?.disabled) {
        setActiveIndex(next);
        return;
      }
    }
  }

  function choose(index: number) {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    setOpen(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!open && ["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      move(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const index = event.key === "Home" ? 0 : options.length - 1;
      setActiveIndex(index);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(activeIndex);
    } else if (event.key === "Escape" || event.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div
      className={`select-control ${open ? "is-open" : ""} ${className}`}
      ref={rootRef}
    >
      <button
        type="button"
        className="select-trigger"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={`${id}-listbox`}
        aria-activedescendant={open ? `${id}-option-${activeIndex}` : undefined}
        disabled={disabled}
        title={title}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={onKeyDown}
      >
        <span>{options[selectedIndex]?.label ?? "Select"}</span>
        <ChevronDown size={17} aria-hidden="true" />
      </button>
      {open && (
        <div
          className="select-menu"
          id={`${id}-listbox`}
          role="listbox"
          aria-label={label}
        >
          {options.map((option, index) => (
            <button
              type="button"
              id={`${id}-option-${index}`}
              className={`select-option ${index === activeIndex ? "is-active" : ""}`}
              role="option"
              aria-selected={option.value === value}
              disabled={option.disabled}
              key={option.value}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(index)}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={16} aria-hidden="true" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={`toggle ${checked ? "on" : ""}`}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  );
}

export function Card({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-heading">
          {title && <h2>{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatusDot({
  state,
}: {
  state: "good" | "warn" | "bad" | "unknown";
}) {
  return <span className={`status-dot status-${state}`} aria-hidden="true" />;
}

export function CapabilityBadge({
  state,
}: {
  state: "available" | "unavailable" | "unverified";
}) {
  return (
    <span className={`badge badge-${state}`}>
      {state === "unverified" ? "unknown" : state}
    </span>
  );
}

export function StatePanel({
  kind,
  title,
  message,
  action,
}: {
  kind: "loading" | "empty" | "error" | "gated" | "success";
  title: string;
  message: string;
  action?: ReactNode;
}) {
  const Icon =
    kind === "error"
      ? AlertCircle
      : kind === "gated"
        ? ShieldAlert
        : CheckCircle2;
  return (
    <div
      className={`state-panel state-${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {kind === "loading" ? (
        <SireIdentity compact thinking />
      ) : (
        <Icon size={20} />
      )}
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
        {action}
      </div>
    </div>
  );
}

export function LoadingRows({ count = 3 }: { count?: number }) {
  return (
    <div className="loading-rows" aria-label="Loading">
      {Array.from({ length: count }, (_, index) => (
        <div className="skeleton" key={index} />
      ))}
    </div>
  );
}

export function RetryButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="secondary" onClick={onClick}>
      <RefreshCw size={14} /> Retry
    </Button>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error ? (
        <span className="field-error">{error}</span>
      ) : hint ? (
        <span className="field-hint">{hint}</span>
      ) : null}
    </label>
  );
}

export function DefinitionList({
  items,
}: {
  items: Array<{ label: string; value: ReactNode }>;
}) {
  return (
    <dl className="definition-list">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

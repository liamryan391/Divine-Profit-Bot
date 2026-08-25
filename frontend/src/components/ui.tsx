import type { LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ChangeEventHandler, InputHTMLAttributes, ReactNode } from "react";
import type { DashboardPayload, WorkerStatus } from "../types";
import { capitalize, cx, slugify } from "../lib/format";

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type Accent = "gold" | "green" | "blue" | "violet" | "red";

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "temple-button-primary",
  secondary: "temple-button-secondary",
  ghost: "temple-button-ghost",
};

const accentText: Record<Accent, string> = {
  gold: "text-temple-gold",
  green: "text-temple-green",
  blue: "text-temple-blue",
  violet: "text-temple-violet",
  red: "text-temple-red",
};

const accentBorder: Record<Accent, string> = {
  gold: "border-l-temple-gold",
  green: "border-l-temple-green",
  blue: "border-l-temple-blue",
  violet: "border-l-temple-violet",
  red: "border-l-temple-red",
};

export function Button({
  children,
  icon: Icon,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon?: LucideIcon; variant?: ButtonVariant }) {
  return (
    <button className={cx("temple-button", buttonVariants[variant], className)} type="button" {...props}>
      {Icon ? <Icon aria-hidden="true" size={17} strokeWidth={2.4} /> : null}
      <span>{children}</span>
    </button>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="temple-badge">{children}</span>;
}

export function StatusPill({ text }: { text: string }) {
  return <div className="temple-badge">{text}</div>;
}

export function WorkerPill({ worker }: { worker: WorkerStatus }) {
  const color = worker.state === "running" ? "bg-temple-green" : worker.state === "stale" ? "bg-temple-gold" : "bg-temple-red";
  const age = worker.age_seconds === null ? "no heartbeat" : `${worker.age_seconds}s ago`;
  return (
    <div className="temple-badge">
      <span className={cx("h-2.5 w-2.5 rounded-full shadow-[0_0_16px_currentColor]", color)} />
      <span>
        Worker: {worker.state} ({age})
      </span>
    </div>
  );
}

export function MetricCard({
  accent,
  icon: Icon,
  label,
  value,
  detail,
}: {
  accent: Accent;
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className={cx("temple-card min-h-[158px] border-l-4", accentBorder[accent])}>
      <div className={cx("mb-4 flex items-center gap-2 font-black", accentText[accent])}>
        <Icon aria-hidden="true" size={20} />
        <p className="m-0">{label}</p>
      </div>
      <strong className={cx("mb-2 block text-[clamp(1.65rem,4vw,2.35rem)] leading-none", accentText[accent])}>
        {value}
      </strong>
      <span className="text-temple-muted">{detail}</span>
    </article>
  );
}

export function Panel({
  title,
  icon: Icon,
  meta,
  actions,
  wide,
  children,
}: {
  title: string;
  icon: LucideIcon;
  meta?: string;
  actions?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <article className={cx("temple-panel", wide && "lg:col-span-2")}>
      <div className="section-heading flex-col items-start sm:flex-row">
        <h2 className="flex items-center gap-2 text-lg font-black">
          <Icon aria-hidden="true" className="text-temple-gold" size={20} />
          {title}
        </h2>
        {actions || (meta ? <Badge>{meta}</Badge> : null)}
      </div>
      {children}
    </article>
  );
}

export function Toolbar({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={cx("flex w-full flex-wrap items-center gap-2 sm:w-auto", className)}>{children}</div>;
}

export function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-h-[62px] rounded-lg bg-white/[0.035] p-2.5">
      <span className="mb-1.5 block text-xs font-black uppercase text-temple-muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function EmptyRow({ children }: { children: ReactNode }) {
  return (
    <div className="temple-row">
      <span className="text-temple-muted">{children}</span>
    </div>
  );
}

export function Field({
  label,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; className?: string }) {
  return (
    <label className={cx("field-label", className)}>
      {label}
      <input className="temple-input" {...props} />
    </label>
  );
}

export function SelectField({
  id,
  label,
  name,
  defaultValue,
  value,
  onChange,
  children,
  className,
  ariaLabel,
}: {
  id?: string;
  label?: string;
  name?: string;
  defaultValue?: string;
  value?: string;
  onChange?: ChangeEventHandler<HTMLSelectElement>;
  children: ReactNode;
  className?: string;
  ariaLabel?: string;
}) {
  const select = (
    <select
      id={id}
      className={cx("temple-input", className)}
      name={name}
      defaultValue={defaultValue}
      value={value}
      onChange={onChange}
      aria-label={ariaLabel || label}
    >
      {children}
    </select>
  );
  if (!label) {
    return select;
  }
  return (
    <label className="field-label">
      {label}
      {select}
    </label>
  );
}

export function StrategySelect({
  label,
  name,
  channels,
  emptyLabel = "Unassigned",
}: {
  label: string;
  name: string;
  channels: DashboardPayload["config"]["channels"];
  emptyLabel?: string;
}) {
  return (
    <SelectField label={label} name={name} defaultValue="">
      <option value="">{emptyLabel}</option>
      {channels.map((channel) => (
        <option key={channel.id || slugify(channel.name)} value={channel.id || slugify(channel.name)}>
          {channel.name}
        </option>
      ))}
    </SelectField>
  );
}

export function MoodSelect({
  label,
  name,
  moods,
  defaultValue,
}: {
  label: string;
  name: string;
  moods: DashboardPayload["config"]["moods"];
  defaultValue: string;
}) {
  return (
    <SelectField label={label} name={name} defaultValue={defaultValue}>
      {Object.keys(moods).map((mood) => (
        <option key={mood} value={mood}>
          {capitalize(mood)}
        </option>
      ))}
    </SelectField>
  );
}

export function Toast({ message }: { message: string }) {
  return (
    <div
      className={cx(
        "fixed bottom-5 right-5 z-50 max-w-[min(420px,calc(100%-36px))] rounded-lg bg-temple-text px-3.5 py-3 font-black text-[#08101c] shadow-2xl transition",
        message ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-4 opacity-0",
      )}
      role="status"
      aria-live="polite"
    >
      {message}
    </div>
  );
}

export function DrawerShell({
  title,
  children,
  open,
}: {
  title: string;
  children: ReactNode;
  open: boolean;
}) {
  return (
    <aside className={cx("temple-panel fixed right-4 top-4 z-40 w-[min(420px,calc(100%-32px))]", !open && "hidden")}>
      <h2 className="mb-4 text-lg font-black">{title}</h2>
      {children}
    </aside>
  );
}

export function ModalShell({
  title,
  children,
  open,
}: {
  title: string;
  children: ReactNode;
  open: boolean;
}) {
  if (!open) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <section className="temple-panel w-[min(560px,100%)]">
        <h2 className="mb-4 text-lg font-black">{title}</h2>
        {children}
      </section>
    </div>
  );
}

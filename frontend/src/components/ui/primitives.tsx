import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */
export function Panel({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("panel", className)} {...props}>
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  subtitle,
  right,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("panel-header", className)}>
      <div className="min-w-0">
        <h3 className="panel-title">{title}</h3>
        {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
      </div>
      {right ? <div className="flex shrink-0 items-center gap-2">{right}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */
type ButtonVariant = "primary" | "secondary" | "ghost" | "outline";
type ButtonSize = "sm" | "md" | "icon";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-ink-950 hover:bg-accent-soft border border-accent/60 shadow-[0_0_18px_-8px_rgba(34,211,238,0.7)] font-semibold",
  secondary:
    "bg-white/[0.04] text-slate-200 hover:bg-white/[0.07] border border-white/[0.08]",
  ghost: "text-slate-400 hover:text-slate-100 hover:bg-white/[0.05] border border-transparent",
  outline:
    "border border-white/[0.12] bg-transparent text-slate-300 hover:border-accent/40 hover:text-slate-100",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-[11.5px] gap-1.5 rounded-md",
  md: "h-[34px] px-3.5 text-[12.5px] gap-2 rounded-md",
  icon: "h-8 w-8 rounded-md",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }
>(function Button({ className, variant = "secondary", size = "md", type = "button", ...props }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45 focus-ring",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...props}
    />
  );
});

/* ------------------------------------------------------------------ */
/* Badge                                                               */
/* ------------------------------------------------------------------ */
type BadgeTone = "accent" | "positive" | "warning" | "negative" | "neutral" | "violet";

const badgeTones: Record<BadgeTone, string> = {
  accent: "border-accent/25 bg-accent/10 text-accent-soft",
  positive: "border-positive/25 bg-positive/10 text-positive",
  warning: "border-warning/25 bg-warning/10 text-warning",
  negative: "border-negative/25 bg-negative/10 text-negative",
  neutral: "border-white/10 bg-white/[0.04] text-slate-400",
  violet: "border-violet-400/25 bg-violet-400/10 text-violet-300",
};

export function Badge({
  tone = "neutral",
  className,
  children,
  dot = false,
}: {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[10.5px] font-medium leading-4",
        badgeTones[tone],
        className,
      )}
    >
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden /> : null}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Inputs                                                              */
/* ------------------------------------------------------------------ */
const controlClass =
  "h-8 rounded-md border border-white/[0.09] bg-ink-900/80 px-2.5 text-[12px] text-slate-200 placeholder:text-slate-600 transition-colors hover:border-white/[0.16] focus:border-accent/50 focus:outline-none focus:ring-1 focus:ring-accent/30";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(controlClass, "w-full", className)} {...props} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select ref={ref} className={cn(controlClass, "cursor-pointer pr-7", className)} {...props}>
        {children}
      </select>
    );
  },
);

/* ------------------------------------------------------------------ */
/* Segmented control                                                   */
/* ------------------------------------------------------------------ */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
  className,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center rounded-md border border-white/[0.08] bg-ink-900/70 p-0.5",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "rounded px-2 py-1 text-[11px] font-medium transition-colors focus-ring",
            value === option.value
              ? "bg-accent/15 text-accent-soft shadow-[inset_0_0_0_1px_rgba(34,211,238,0.2)]"
              : "text-slate-500 hover:text-slate-200",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Skeleton / spinner                                                  */
/* ------------------------------------------------------------------ */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded bg-white/[0.045]", className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-current border-t-transparent",
        className,
      )}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Empty / error states                                                */
/* ------------------------------------------------------------------ */
export function StateBlock({
  icon,
  title,
  description,
  action,
  tone = "neutral",
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "negative";
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-12 text-center">
      {icon ? (
        <div
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-lg border",
            tone === "negative"
              ? "border-negative/20 bg-negative/10 text-negative"
              : "border-white/[0.08] bg-white/[0.03] text-slate-500",
          )}
        >
          {icon}
        </div>
      ) : null}
      <div>
        <p className="text-[13px] font-medium text-slate-200">{title}</p>
        {description ? <p className="mx-auto mt-1 max-w-md text-[11.5px] leading-5 text-slate-500">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

import { cn } from "@/utils/cn";

export function Tabs<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string; count?: number }[];
  className?: string;
}) {
  return (
    <div role="tablist" className={cn("no-scrollbar flex gap-1 overflow-x-auto rounded-xl bg-brand-100/70 p-1", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          type="button"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            o.value === value ? "bg-white text-brand-700 shadow-sm" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
          {typeof o.count === "number" && <span className="rounded-full bg-brand-100 px-1.5 text-xs text-brand-700">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

import { cn } from "@/utils/cn";

export const inputClasses = (invalid?: boolean, extra?: string) =>
  cn(
    "h-10 w-full rounded-xl border bg-white px-3 text-sm text-ink placeholder:text-muted/70 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-300 disabled:bg-surface disabled:text-muted",
    invalid ? "border-rose-400 focus:ring-rose-200" : "border-line hover:border-brand-300 focus:border-brand-400",
    extra,
  );

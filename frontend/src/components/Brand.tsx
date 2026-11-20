import { Link } from "react-router-dom";

import { cn } from "@/utils/cn";

export function Logo({ className, iconOnly, to = "/" }: { className?: string; iconOnly?: boolean; to?: string }) {
  return (
    <Link to={to} className={cn("inline-flex items-center gap-2", className)} aria-label="MediCart home">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500 text-white shadow-sm">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
          <path d="M7 17 17 7" />
          <path d="M12 12l5-5" stroke="#EEE7FA" />
        </svg>
      </span>
      {!iconOnly && (
        <span className="text-xl font-bold tracking-tight text-ink">
          Medi<span className="text-brand-500">Cart</span>
        </span>
      )}
    </Link>
  );
}

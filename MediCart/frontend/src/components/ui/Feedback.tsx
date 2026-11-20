import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import type { OrderStatus, VerificationStatus } from "@/types";
import { cn } from "@/utils/cn";
import { humanise } from "@/utils/format";
import { orderStatusLabel, verificationLabel } from "@/utils/labels";

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <div className={cn("flex items-center justify-center gap-2 py-10 text-muted", className)} role="status">
      <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-brand-100/80", className)} />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-surface/60 px-6 py-12 text-center",
        className,
      )}
    >
      {Icon && (
        <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-500">
          <Icon className="h-6 w-6" />
        </span>
      )}
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

type Tone = "info" | "success" | "warning" | "error";

const toneStyles: Record<Tone, { box: string; icon: LucideIcon; iconColor: string }> = {
  info: { box: "border-brand-200 bg-brand-50 text-brand-900", icon: Info, iconColor: "text-brand-500" },
  success: { box: "border-emerald-200 bg-emerald-50 text-emerald-900", icon: CheckCircle2, iconColor: "text-emerald-600" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-900", icon: AlertTriangle, iconColor: "text-amber-600" },
  error: { box: "border-rose-200 bg-rose-50 text-rose-900", icon: XCircle, iconColor: "text-rose-600" },
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  const style = toneStyles[tone];
  const Icon = style.icon;
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex gap-3 rounded-xl border p-3.5 text-sm", style.box, className)}>
      <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", style.iconColor)} />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  );
}

type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "bg-brand-50 text-muted ring-line",
  brand: "bg-brand-100 text-brand-700 ring-brand-200",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  danger: "bg-rose-50 text-rose-700 ring-rose-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
};

export function Badge({ tone = "neutral", children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
        badgeTones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const orderTones: Record<OrderStatus, BadgeTone> = {
  placed: "brand",
  verification_pending: "warning",
  verified: "info",
  processing: "info",
  packed: "info",
  shipped: "brand",
  delivered: "success",
  cancelled: "danger",
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return <Badge tone={orderTones[status] ?? "neutral"}>{orderStatusLabel[status] ?? humanise(status)}</Badge>;
}

const verificationTones: Record<VerificationStatus, BadgeTone> = {
  not_required: "neutral",
  pending: "warning",
  approved: "success",
  rejected: "danger",
  clarification_requested: "info",
};

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  return <Badge tone={verificationTones[status] ?? "neutral"}>{verificationLabel[status] ?? humanise(status)}</Badge>;
}

export function PaymentBadge({ status }: { status: string }) {
  const tone: BadgeTone =
    status === "paid" ? "success" : status === "refunded" ? "info" : status === "cancelled" ? "danger" : "warning";
  const label = status === "cod_pending" ? "Cash on delivery" : humanise(status);
  return <Badge tone={tone}>{label}</Badge>;
}

export function MatchBadge({ status }: { status: string }) {
  const map: Record<string, { tone: BadgeTone; label: string }> = {
    exact: { tone: "success", label: "Exact match" },
    possible: { tone: "info", label: "Possible match" },
    uncertain: { tone: "warning", label: "Uncertain match" },
    none: { tone: "danger", label: "No match found" },
  };
  const entry = map[status] ?? { tone: "neutral" as BadgeTone, label: humanise(status) };
  return <Badge tone={entry.tone}>{entry.label}</Badge>;
}

import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/utils/cn";

export function Card({ children, className, padded = true }: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div className={cn("rounded-2xl border border-line bg-white shadow-card", padded && "p-5", className)}>{children}</div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div>
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-wide text-brand-500">{eyebrow}</p>}
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Pagination({
  page,
  pages,
  onChange,
  total,
  className,
}: {
  page: number;
  pages: number;
  total?: number;
  onChange: (page: number) => void;
  className?: string;
}) {
  if (pages <= 1) return null;
  return (
    <nav className={cn("flex items-center justify-between gap-3", className)} aria-label="Pagination">
      <p className="text-sm text-muted">
        Page {page} of {pages}
        {typeof total === "number" && ` · ${total} results`}
      </p>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </nav>
  );
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;
  const width = size === "sm" ? "max-w-sm" : size === "lg" ? "max-w-2xl" : "max-w-lg";
  return (
    <div className="fixed inset-0 z-[90] flex items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onClick={(e) => e.stopPropagation()}
        className={cn("w-full rounded-t-2xl bg-white shadow-pop sm:rounded-2xl", width, "max-h-[92vh] flex flex-col")}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 id="modal-title" className="text-lg font-semibold text-ink">
              {title}
            </h2>
            {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-brand-50 hover:text-ink" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children && <div className="scrollbar-thin flex-1 overflow-y-auto px-5 py-4">{children}</div>}
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-4">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  tone = "primary",
  loading,
  children,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  tone?: "primary" | "danger";
  loading?: boolean;
  children?: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant={tone} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Modal>
  );
}

export function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <Card className="flex items-start justify-between gap-3">
      <div>
        <p className="text-sm text-muted">{label}</p>
        <p className="mt-1 text-2xl font-bold tracking-tight text-ink">{value}</p>
        {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      </div>
      {icon && <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-brand-600">{icon}</span>}
    </Card>
  );
}

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto rounded-2xl border border-line bg-white shadow-card", className)}>
      <table className="min-w-full divide-y divide-line text-sm">{children}</table>
    </div>
  );
}

export const th = "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted";
export const td = "px-4 py-3 align-middle text-ink";

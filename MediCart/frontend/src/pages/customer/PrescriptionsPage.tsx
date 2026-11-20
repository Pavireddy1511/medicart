import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileText, FileUp } from "lucide-react";
import { Link } from "react-router-dom";

import { LinkButton } from "@/components/ui/Button";
import { Badge, EmptyState, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { PageHeader } from "@/components/ui/Layout";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { prescriptionApi } from "@/services/api";
import { formatDateTime, humanise } from "@/utils/format";

export default function PrescriptionsPage() {
  useDocumentTitle("My prescriptions");
  const { data, isLoading } = useQuery({ queryKey: ["prescriptions"], queryFn: prescriptionApi.list });

  return (
    <div className="space-y-5">
      <PageHeader
        title="My prescriptions"
        description="Only the extracted text and your confirmed medicines are kept. Original images are never stored."
        actions={<LinkButton to="/prescriptions/upload" leftIcon={<FileUp className="h-4 w-4" />}>Upload new</LinkButton>}
      />
      {isLoading ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <EmptyState icon={FileText} title="No prescriptions yet" description="Upload a photo or PDF of a prescription to get started." action={<LinkButton to="/prescriptions/upload">Upload prescription</LinkButton>} />
      ) : (
        <ul className="space-y-3">
          {data.map((p) => (
            <li key={p.id}>
              <Link to={`/prescriptions/${p.id}`} className="flex items-center gap-4 rounded-2xl border border-line bg-white p-4 shadow-card transition-colors hover:border-brand-300">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-600">
                  <FileText className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">Prescription #{p.id}</p>
                  <p className="text-xs text-muted">
                    {formatDateTime(p.created_at)} · {p.item_count} medicine{p.item_count === 1 ? "" : "s"} · {humanise(p.document_type)}
                  </p>
                </div>
                <div className="hidden flex-wrap items-center justify-end gap-2 sm:flex">
                  {p.user_confirmation_status === "pending" ? <Badge tone="warning">Needs your review</Badge> : <Badge tone="success">Confirmed</Badge>}
                  <VerificationBadge status={p.pharmacist_verification_status} />
                </div>
                <ChevronRight className="h-5 w-5 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

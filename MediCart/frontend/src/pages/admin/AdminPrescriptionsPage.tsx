import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge, EmptyState, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { PageHeader, Pagination, Table, td, th } from "@/components/ui/Layout";
import { Tabs } from "@/components/ui/Tabs";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi } from "@/services/api";
import type { VerificationStatus } from "@/types";
import { formatDateTime, humanise, percent } from "@/utils/format";

type Filter = "" | VerificationStatus;

export default function AdminPrescriptionsPage() {
  useDocumentTitle("Prescriptions");
  const [status, setStatus] = useState<Filter>("");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "prescriptions", status, page],
    queryFn: () => adminApi.prescriptions({ status: status || undefined, page, page_size: 20 }),
    placeholderData: (prev) => prev,
  });

  return (
    <div className="space-y-5">
      <PageHeader title="Prescriptions" description="Every upload, how it was read, and where verification stands. AI output here is an interpretation, not a verified document." />
      <Tabs
        value={status}
        onChange={(v) => { setStatus(v); setPage(1); }}
        options={[
          { value: "", label: "All" },
          { value: "pending", label: "Pending verification" },
          { value: "clarification_requested", label: "Clarification" },
          { value: "approved", label: "Approved" },
          { value: "rejected", label: "Rejected" },
          { value: "not_required", label: "No verification needed" },
        ]}
      />
      {isLoading && !data ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No prescriptions" />
      ) : (
        <>
          <Table>
            <thead className="bg-surface">
              <tr>
                <th className={th}>Prescription</th>
                <th className={th}>Customer</th>
                <th className={th}>Recognition</th>
                <th className={th}>Items</th>
                <th className={th}>Customer</th>
                <th className={th}>Pharmacist</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.items.map((p) => (
                <tr key={p.id} className="hover:bg-brand-50/40">
                  <td className={td}>
                    <Link to={`/admin/prescriptions/${p.id}`} className="font-semibold text-brand-600 hover:underline">#{p.id}</Link>
                    <p className="text-xs text-muted">{formatDateTime(p.created_at)} · {humanise(p.document_type)}</p>
                  </td>
                  <td className={td}>{p.customer_name}</td>
                  <td className={`${td} text-xs`}>
                    <p>OCR {p.ocr_engine ?? "none"} · {percent(p.ocr_confidence)}</p>
                    <p className="text-muted">AI {humanise(p.ai_review_status)}</p>
                  </td>
                  <td className={td}>
                    <div className="flex gap-1">
                      <Badge tone="neutral">{p.item_count}</Badge>
                      {p.uncertain_item_count > 0 && <Badge tone="warning">{p.uncertain_item_count} uncertain</Badge>}
                    </div>
                  </td>
                  <td className={td}>{p.user_confirmation_status === "confirmed" ? <Badge tone="success">Confirmed</Badge> : <Badge tone="warning">Pending</Badge>}</td>
                  <td className={td}><VerificationBadge status={p.pharmacist_verification_status} /></td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}

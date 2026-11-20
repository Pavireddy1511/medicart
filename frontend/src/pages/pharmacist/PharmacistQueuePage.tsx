import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge, EmptyState, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { PageHeader, Table, td, th } from "@/components/ui/Layout";
import { Tabs } from "@/components/ui/Tabs";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { pharmacistApi } from "@/services/api";
import { formatDateTime, humanise, percent } from "@/utils/format";

type Filter = "open" | "clarification_requested" | "approved" | "rejected" | "all";

export default function PharmacistQueuePage() {
  useDocumentTitle("Verification queue");
  const [filter, setFilter] = useState<Filter>("open");
  const { data, isLoading } = useQuery({
    queryKey: ["pharmacist", "requests", filter],
    queryFn: () => pharmacistApi.requests(filter === "open" ? undefined : filter),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="Verification queue"
        description="Prescriptions customers asked a pharmacist to review. Orders linked to them wait here until you decide."
      />
      <Tabs
        value={filter}
        onChange={setFilter}
        options={[
          { value: "open", label: "Needs action" },
          { value: "clarification_requested", label: "Awaiting customer" },
          { value: "approved", label: "Approved" },
          { value: "rejected", label: "Rejected" },
          { value: "all", label: "All" },
        ]}
      />
      {isLoading ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <EmptyState icon={ClipboardCheck} title="Nothing to verify" description="New requests appear here as soon as customers confirm their prescriptions." />
      ) : (
        <Table>
          <thead className="bg-surface">
            <tr>
              <th className={th}>Prescription</th>
              <th className={th}>Customer</th>
              <th className={th}>Medicines</th>
              <th className={th}>Recognition</th>
              <th className={th}>Status</th>
              <th className={th}>Updated</th>
              <th className={th}></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.map((r) => (
              <tr key={r.prescription_id} className="hover:bg-brand-50/40">
                <td className={td}>
                  <p className="font-semibold">#{r.prescription_id}</p>
                  <p className="text-xs text-muted">{humanise(r.document_type)}</p>
                </td>
                <td className={td}>
                  <p className="font-medium">{r.customer_name}</p>
                  <p className="text-xs text-muted">{r.customer_mobile_masked}</p>
                </td>
                <td className={td}>
                  <div className="flex flex-wrap gap-1">
                    <Badge tone="neutral">{r.item_count} total</Badge>
                    {r.rx_item_count > 0 && <Badge tone="warning">{r.rx_item_count} Rx</Badge>}
                    {r.uncertain_item_count > 0 && <Badge tone="danger">{r.uncertain_item_count} uncertain</Badge>}
                  </div>
                </td>
                <td className={td}>
                  <p className="text-xs">
                    AI: <span className="font-medium">{humanise(r.ai_review_status)}</span>
                  </p>
                  <p className="text-xs text-muted">OCR confidence {percent(r.ocr_confidence)}</p>
                </td>
                <td className={td}>
                  <VerificationBadge status={r.pharmacist_verification_status} />
                </td>
                <td className={`${td} whitespace-nowrap text-xs text-muted`}>{formatDateTime(r.updated_at)}</td>
                <td className={`${td} text-right`}>
                  <Link to={`/pharmacist/requests/${r.prescription_id}`} className="text-sm font-semibold text-brand-600 hover:underline">
                    Review
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}

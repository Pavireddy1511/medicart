import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { Checkbox } from "@/components/ui/Form";
import { PageHeader, Table, td, th } from "@/components/ui/Layout";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { pharmacistApi } from "@/services/api";
import type { VerificationStatus } from "@/types";
import { formatDateTime } from "@/utils/format";

export default function PharmacistHistoryPage() {
  useDocumentTitle("Verification history");
  const [mine, setMine] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["pharmacist", "history", mine], queryFn: () => pharmacistApi.history(mine) });

  return (
    <div className="space-y-5">
      <PageHeader title="Verification history" description="Every decision recorded on a prescription." actions={<Checkbox label="Only my decisions" checked={mine} onChange={(e) => setMine(e.target.checked)} />} />
      {isLoading ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <EmptyState icon={History} title="No decisions yet" />
      ) : (
        <Table>
          <thead className="bg-surface">
            <tr>
              <th className={th}>When</th>
              <th className={th}>Prescription</th>
              <th className={th}>Decision</th>
              <th className={th}>Pharmacist</th>
              <th className={th}>Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.map((h) => (
              <tr key={h.id}>
                <td className={`${td} whitespace-nowrap text-xs text-muted`}>{formatDateTime(h.verified_at)}</td>
                <td className={td}>
                  <Link to={`/pharmacist/requests/${h.prescription_id}`} className="font-semibold text-brand-600 hover:underline">#{h.prescription_id}</Link>
                </td>
                <td className={td}><VerificationBadge status={h.verification_status as VerificationStatus} /></td>
                <td className={td}>{h.pharmacist_name ?? "-"}</td>
                <td className={`${td} max-w-md text-xs text-muted`}>{h.notes ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}

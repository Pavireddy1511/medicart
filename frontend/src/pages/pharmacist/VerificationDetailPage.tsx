import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, HelpCircle, X } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { Button, LinkButton } from "@/components/ui/Button";
import { Alert, Badge, EmptyState, MatchBadge, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { Textarea } from "@/components/ui/Form";
import { Card, ConfirmDialog, PageHeader, Table, td, th } from "@/components/ui/Layout";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi, pharmacistApi } from "@/services/api";
import { toApiError } from "@/services/http";
import { formatDateTime, humanise, percent } from "@/utils/format";

type Decision = "approved" | "rejected" | "clarification_requested";

const decisionCopy: Record<Decision, { title: string; label: string; tone: "primary" | "danger" }> = {
  approved: { title: "Approve this prescription?", label: "Approve", tone: "primary" },
  rejected: { title: "Reject this prescription?", label: "Reject", tone: "danger" },
  clarification_requested: { title: "Ask the customer for clarification?", label: "Request clarification", tone: "primary" },
};

export default function VerificationDetailPage() {
  const { id } = useParams();
  const prescriptionId = Number(id);
  const location = useLocation();
  const isAdminArea = location.pathname.startsWith("/admin");
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState<Decision | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["verification", prescriptionId],
    queryFn: () => (isAdminArea ? adminApi.prescription(prescriptionId) : pharmacistApi.request(prescriptionId)),
  });
  useDocumentTitle(`Prescription #${prescriptionId}`);

  const decide = useMutation({
    mutationFn: (status: Decision) => pharmacistApi.decide({ prescription_id: prescriptionId, status, notes: notes.trim() || undefined }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["verification", prescriptionId], updated);
      queryClient.invalidateQueries({ queryKey: ["pharmacist"] });
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      setPending(null);
      setNotes("");
      toast.success(`Prescription ${humanise(updated.pharmacist_verification_status).toLowerCase()}`);
    },
    onError: (err) => {
      setPending(null);
      toast.error("Could not save the decision", toApiError(err).message);
    },
  });

  if (isLoading) return <Spinner label="Loading prescription" />;
  if (isError || !data) return <EmptyState title="Prescription not found" action={<LinkButton to={isAdminArea ? "/admin/prescriptions" : "/pharmacist"}>Back</LinkButton>} />;

  const open = ["pending", "clarification_requested"].includes(data.pharmacist_verification_status);
  const canDecide = open && data.user_confirmation_status === "confirmed" && (user?.role === "pharmacist" || user?.role === "admin");
  const needsNotes = pending === "rejected" || pending === "clarification_requested";
  const included = data.items.filter((i) => i.included);
  const excluded = data.items.filter((i) => !i.included);

  return (
    <div className="space-y-5">
      <Link to={isAdminArea ? "/admin/prescriptions" : "/pharmacist"} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> Back to {isAdminArea ? "prescriptions" : "queue"}
      </Link>
      <PageHeader
        eyebrow={`Uploaded ${formatDateTime(data.created_at)}`}
        title={`Prescription #${data.id}`}
        description={`${data.customer_name} · ${data.customer_mobile_masked}`}
        actions={
          <>
            {data.user_confirmation_status === "confirmed" ? <Badge tone="success">Customer confirmed</Badge> : <Badge tone="warning">Not yet confirmed by customer</Badge>}
            <VerificationBadge status={data.pharmacist_verification_status} />
          </>
        }
      />

      <Alert tone="info" title="Original image is not available">
        MediCart does not store prescription images. Only the OCR text and the structured medicines, including the customer's edits, are kept.
        Verify against what the customer confirmed and ask for clarification if anything is unclear.
      </Alert>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <Card padded={false}>
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <h2 className="text-base font-semibold text-ink">Medicines ({included.length})</h2>
              <p className="text-xs text-muted">
                {humanise(data.document_type)} · OCR {data.ocr_engine ?? "unavailable"} · confidence {percent(data.ocr_confidence)} · AI {humanise(data.ai_review_status)}
                {data.ai_model && ` (${data.ai_model})`}
              </p>
            </div>
            <Table className="rounded-none border-0 shadow-none">
              <thead className="bg-surface">
                <tr>
                  <th className={th}>As written / read</th>
                  <th className={th}>Details</th>
                  <th className={th}>Catalogue match</th>
                  <th className={th}>Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {included.map((item) => (
                  <tr key={item.id}>
                    <td className={td}>
                      <p className="font-semibold">{item.extracted_name}</p>
                      {item.original_text && item.original_text !== item.extracted_name && <p className="text-xs text-muted">OCR: “{item.original_text}”</p>}
                    </td>
                    <td className={`${td} text-xs`}>
                      <p>{[item.strength_text, item.formulation_text].filter(Boolean).join(" · ") || <span className="text-muted">no strength</span>}</p>
                      <p className="text-muted">{[item.dosage_text, item.frequency_text, item.duration_text].filter(Boolean).join(" · ") || "no dose / frequency"}</p>
                    </td>
                    <td className={td}>
                      <div className="flex flex-col gap-1">
                        <MatchBadge status={item.matched_medicine ? item.match_status : "none"} />
                        {item.matched_medicine && (
                          <p className="text-xs">
                            {item.matched_medicine.medicine_name} {item.matched_medicine.strength}
                            {item.matched_medicine.prescription_required && <Badge tone="warning" className="ml-1">Rx</Badge>}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className={td}>
                      <div className="flex flex-wrap gap-1">
                        {item.uncertainty_status === "uncertain" && <Badge tone="warning">Uncertain: {item.uncertain_fields.join(", ") || "review"}</Badge>}
                        {item.user_edited && <Badge tone="info">Edited by customer</Badge>}
                      </div>
                    </td>
                  </tr>
                ))}
                {included.length === 0 && (
                  <tr>
                    <td className={`${td} text-muted`} colSpan={4}>No medicines included.</td>
                  </tr>
                )}
              </tbody>
            </Table>
            {excluded.length > 0 && (
              <p className="px-4 py-3 text-xs text-muted">Excluded by the customer: {excluded.map((i) => i.extracted_name).join(", ")}</p>
            )}
          </Card>

          <div className="grid gap-5 md:grid-cols-2">
            <Card>
              <h2 className="text-sm font-semibold text-ink">Customer notes</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm text-ink">{data.customer_notes || <span className="text-muted">None</span>}</p>
              {data.linked_order_numbers.length > 0 && (
                <p className="mt-3 text-xs text-muted">Linked orders: {data.linked_order_numbers.join(", ")}</p>
              )}
            </Card>
            <Card>
              <h2 className="text-sm font-semibold text-ink">Extracted text</h2>
              <pre className="scrollbar-thin mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 font-mono text-xs text-ink">
                {data.extracted_text || "No text was recognised."}
              </pre>
            </Card>
          </div>
        </div>

        <div className="space-y-5">
          {canDecide ? (
            <Card className="space-y-3">
              <h2 className="text-base font-semibold text-ink">Decision</h2>
              <Textarea label="Notes to the customer" hint="Required when rejecting or asking for clarification." value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} />
              <div className="grid gap-2">
                <Button leftIcon={<Check className="h-4 w-4" />} onClick={() => setPending("approved")}>Approve</Button>
                <Button variant="secondary" leftIcon={<HelpCircle className="h-4 w-4" />} onClick={() => setPending("clarification_requested")}>Request clarification</Button>
                <Button variant="danger" leftIcon={<X className="h-4 w-4" />} onClick={() => setPending("rejected")}>Reject</Button>
              </div>
              <p className="text-xs text-muted">Approving releases any orders waiting on this prescription. Rejecting cancels them and restocks the items.</p>
            </Card>
          ) : (
            <Card>
              <h2 className="text-base font-semibold text-ink">Decision</h2>
              <p className="mt-2 text-sm text-muted">
                {data.user_confirmation_status !== "confirmed"
                  ? "The customer has not confirmed this prescription yet, so it cannot be verified."
                  : `This prescription is already ${humanise(data.pharmacist_verification_status).toLowerCase()}.`}
              </p>
            </Card>
          )}

          <Card>
            <h2 className="text-sm font-semibold text-ink">History</h2>
            {data.verifications.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No decisions yet.</p>
            ) : (
              <ul className="mt-2 space-y-2 text-xs">
                {data.verifications.map((v) => (
                  <li key={v.id} className="rounded-lg bg-surface p-2">
                    <p className="font-semibold text-ink">{humanise(v.verification_status)} · {v.pharmacist_name ?? "Pharmacist"}</p>
                    <p className="text-muted">{formatDateTime(v.verified_at)}</p>
                    {v.notes && <p className="mt-1 text-ink">{v.notes}</p>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={pending !== null}
        onClose={() => setPending(null)}
        onConfirm={() => pending && decide.mutate(pending)}
        loading={decide.isPending}
        title={pending ? decisionCopy[pending].title : ""}
        description={needsNotes && !notes.trim() ? "Add a note for the customer before continuing." : undefined}
        confirmLabel={pending ? decisionCopy[pending].label : "Confirm"}
        tone={pending ? decisionCopy[pending].tone : "primary"}
      >
        {needsNotes && !notes.trim() && <Alert tone="warning">A note is required for this decision.</Alert>}
        {notes.trim() && <p className="text-sm text-muted">Note: {notes}</p>}
      </ConfirmDialog>
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { MedicinePicker } from "@/components/MedicinePicker";
import { Button, LinkButton } from "@/components/ui/Button";
import { Alert, Badge, EmptyState, MatchBadge, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { Checkbox, Input, Select, Textarea } from "@/components/ui/Form";
import { Card, PageHeader } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { CART_KEY, useCart } from "@/hooks/useCart";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { prescriptionApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { ConfirmItemInput, ConfirmResponse, Medicine, NewItemInput, Prescription, PrescriptionItem } from "@/types";
import { analysisStore } from "@/utils/analysisStore";
import { cn } from "@/utils/cn";
import { formatDateTime, humanise, percent } from "@/utils/format";

type Draft = ConfirmItemInput & { candidates: PrescriptionItem["candidates"]; original: PrescriptionItem };
type NewDraft = NewItemInput & { key: number; medicine_name?: string };

function toDraft(item: PrescriptionItem): Draft {
  return {
    item_id: item.id,
    extracted_name: item.extracted_name,
    strength_text: item.strength_text ?? "",
    formulation_text: item.formulation_text ?? "",
    dosage_text: item.dosage_text ?? "",
    frequency_text: item.frequency_text ?? "",
    duration_text: item.duration_text ?? "",
    matched_medicine_id: item.matched_medicine?.id ?? null,
    included: item.included,
    candidates: item.candidates,
    original: item,
  };
}

const fieldLabel: Record<string, string> = {
  extracted_name: "name",
  strength: "strength",
  strength_text: "strength",
  frequency_text: "frequency",
  duration_text: "duration",
  dosage_text: "dose",
  formulation: "formulation",
  match: "catalogue match",
};

function ItemEditor({
  draft,
  editable,
  onChange,
}: {
  draft: Draft;
  editable: boolean;
  onChange: (next: Draft) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const item = draft.original;
  const uncertain = item.uncertain_fields.map((f) => fieldLabel[f] ?? f);
  const selectedCandidate = draft.candidates.find((c) => c.medicine_id === draft.matched_medicine_id);
  const selectedName =
    selectedCandidate?.medicine_name ??
    (item.matched_medicine && item.matched_medicine.id === draft.matched_medicine_id ? item.matched_medicine.medicine_name : null);

  const set = (key: keyof ConfirmItemInput, value: string | number | boolean | null) => onChange({ ...draft, [key]: value });

  return (
    <div className={cn("rounded-2xl border bg-white p-4 shadow-card", draft.included ? "border-line" : "border-dashed border-line opacity-70")}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <MatchBadge status={draft.matched_medicine_id ? (item.match_status === "exact" ? "exact" : "possible") : item.match_status} />
            {item.uncertainty_status === "uncertain" && (
              <Badge tone="warning">
                <AlertTriangle className="h-3 w-3" /> Check {uncertain.join(", ") || "details"}
              </Badge>
            )}
            {item.user_edited && <Badge tone="info">Edited by you</Badge>}
          </div>
          {item.original_text && <p className="mt-1.5 text-xs text-muted">Read as: “{item.original_text}”</p>}
        </div>
        {editable && (
          <Checkbox label="Include" checked={draft.included} onChange={(e) => set("included", e.target.checked)} />
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Input label="Medicine name" value={draft.extracted_name} onChange={(e) => set("extracted_name", e.target.value)} disabled={!editable} required />
        <Input label="Strength" placeholder="e.g. 500 mg" value={draft.strength_text ?? ""} onChange={(e) => set("strength_text", e.target.value)} disabled={!editable} />
        <Input label="Form" placeholder="tablet, syrup…" value={draft.formulation_text ?? ""} onChange={(e) => set("formulation_text", e.target.value)} disabled={!editable} />
        <Input label="Dose" placeholder="e.g. 1 tablet" value={draft.dosage_text ?? ""} onChange={(e) => set("dosage_text", e.target.value)} disabled={!editable} />
        <Input label="Frequency" placeholder="e.g. 1-0-1" value={draft.frequency_text ?? ""} onChange={(e) => set("frequency_text", e.target.value)} disabled={!editable} />
        <Input label="Duration" placeholder="e.g. 5 days" value={draft.duration_text ?? ""} onChange={(e) => set("duration_text", e.target.value)} disabled={!editable} />
      </div>

      <div className="mt-3 rounded-xl bg-surface p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-ink">Catalogue match</p>
          {editable && draft.candidates.length > 0 && (
            <p className="text-xs text-muted">{draft.matched_medicine_id ? "Tap another option to change it" : "Tap the right product"}</p>
          )}
        </div>
        {draft.candidates.length > 0 && editable ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {draft.candidates.map((c) => {
              const selected = c.medicine_id === draft.matched_medicine_id;
              return (
                <li key={c.medicine_id}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => set("matched_medicine_id", selected ? null : c.medicine_id)}
                    className={cn(
                      "flex flex-col items-start rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                      selected ? "border-brand-500 bg-brand-50 text-brand-800" : "border-line bg-white text-ink hover:border-brand-300",
                    )}
                  >
                    <span className="font-semibold">
                      {c.medicine_name}
                      {c.prescription_required && <span className="ml-1.5 rounded-full bg-amber-100 px-1.5 text-[10px] font-bold text-amber-800">Rx</span>}
                    </span>
                    <span className="text-xs text-muted">
                      {[c.generic_name, c.formulation, c.strength].filter(Boolean).join(" · ") || " "}
                    </span>
                    <span className="text-[11px] text-muted">
                      {Math.round(c.score)}% match{c.matched_on.startsWith("composition") ? " by ingredient" : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-muted">{selectedName ?? "Nothing in the catalogue resembles this line yet."}</p>
        )}
        {editable && (
          <div className="mt-2">
            {pickerOpen ? (
              <MedicinePicker
                autoFocus
                placeholder="Search the catalogue for the right medicine"
                onSelect={(m: Medicine) => {
                  onChange({
                    ...draft,
                    matched_medicine_id: m.id,
                    candidates: [
                      {
                        medicine_id: m.id,
                        medicine_name: m.medicine_name,
                        brand_name: m.brand_name,
                        generic_name: m.generic_name,
                        strength: m.strength,
                        formulation: m.formulation,
                        prescription_required: m.prescription_required,
                        score: 100,
                        matched_on: "manual",
                      },
                      ...draft.candidates.filter((c) => c.medicine_id !== m.id),
                    ],
                  });
                  setPickerOpen(false);
                }}
              />
            ) : (
              <button type="button" onClick={() => setPickerOpen(true)} className="text-xs font-semibold text-brand-600 hover:underline">
                Search the catalogue instead
              </button>
            )}
          </div>
        )}
        {selectedName && draft.candidates.find((c) => c.medicine_id === draft.matched_medicine_id)?.prescription_required && (
          <p className="mt-2 text-xs text-amber-700">Prescription medicine: it will be ordered against this prescription.</p>
        )}
      </div>
    </div>
  );
}

function AddToCartRow({ item }: { item: PrescriptionItem }) {
  const { add } = useCart();
  const medicine = item.matched_medicine;
  const products = medicine?.products.filter((p) => p.is_active) ?? [];
  const [productId, setProductId] = useState<number | null>(products.find((p) => p.in_stock)?.id ?? products[0]?.id ?? null);
  if (!medicine) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {products.length > 1 && (
        <Select
          aria-label="Pack size"
          className="w-48"
          value={productId ? String(productId) : ""}
          options={products.map((p) => ({ value: String(p.id), label: `${p.pack_size} · ₹${p.price.toFixed(2)}${p.in_stock ? "" : " (out of stock)"}` }))}
          onChange={(e) => setProductId(Number(e.target.value))}
        />
      )}
      <Button
        size="sm"
        disabled={!item.can_add_to_cart || !productId}
        loading={add.isPending}
        leftIcon={<ShoppingCart className="h-4 w-4" />}
        onClick={() => productId && add.mutate({ productId })}
      >
        Add to cart
      </Button>
      {!item.can_add_to_cart && item.blocked_reason && <span className="text-xs text-muted">{item.blocked_reason}</span>}
    </div>
  );
}

export default function PrescriptionReviewPage() {
  const { id } = useParams();
  const prescriptionId = Number(id);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const sessionData = analysisStore.get(prescriptionId);

  const { data: prescription, isLoading, isError } = useQuery({
    queryKey: ["prescription", prescriptionId],
    queryFn: () => prescriptionApi.get(prescriptionId),
    initialData: sessionData?.prescription,
  });
  useDocumentTitle(`Prescription #${prescriptionId}`);

  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [newItems, setNewItems] = useState<NewDraft[]>([]);
  const [notes, setNotes] = useState("");
  const [requestReview, setRequestReview] = useState(false);
  const [showText, setShowText] = useState(false);
  const [reviewMessage, setReviewMessage] = useState("");

  // Re-seed the editable copy whenever the server record changes (load, confirm, decision).
  const [syncedFrom, setSyncedFrom] = useState<Prescription | null>(null);
  if (prescription && prescription !== syncedFrom) {
    setSyncedFrom(prescription);
    setDrafts(prescription.items.map(toDraft));
    setNotes(prescription.customer_notes ?? "");
  }

  const editable = useMemo(
    () => Boolean(prescription && prescription.pharmacist_verification_status !== "approved"),
    [prescription],
  );

  const confirm = useMutation({
    mutationFn: () =>
      prescriptionApi.confirm({
        prescription_id: prescriptionId,
        items: drafts.map((d) => ({
          item_id: d.item_id,
          extracted_name: d.extracted_name,
          strength_text: d.strength_text,
          formulation_text: d.formulation_text,
          dosage_text: d.dosage_text,
          frequency_text: d.frequency_text,
          duration_text: d.duration_text,
          matched_medicine_id: d.matched_medicine_id,
          included: d.included,
        })),
        new_items: newItems.map((n) => ({
          extracted_name: n.extracted_name,
          strength_text: n.strength_text,
          formulation_text: n.formulation_text,
          dosage_text: n.dosage_text,
          frequency_text: n.frequency_text,
          duration_text: n.duration_text,
          matched_medicine_id: n.matched_medicine_id,
        })),
        customer_notes: notes.trim() || null,
        request_pharmacist_review: requestReview,
        add_to_cart: true,
      }),
    onSuccess: (updated: ConfirmResponse) => {
      queryClient.setQueryData(["prescription", prescriptionId], updated);
      queryClient.invalidateQueries({ queryKey: ["prescriptions"] });
      queryClient.invalidateQueries({ queryKey: CART_KEY });
      setNewItems([]);
      const added = updated.cart_added.length;
      const skipped = updated.cart_skipped.filter((s) => s.reason !== "Already in your cart");
      const skippedText = skipped.length
        ? ` Not added: ${skipped.map((s) => `${s.name} (${s.reason.toLowerCase()})`).join(", ")}.`
        : "";
      const reviewText = updated.pharmacist_verification_status === "pending" ? " A pharmacist will also review it." : "";
      if (added > 0) {
        toast.success(`${added} medicine${added === 1 ? "" : "s"} added to your cart`, `${reviewText}${skippedText}`.trim() || undefined);
        navigate("/cart");
      } else {
        toast.info("Prescription saved", `Nothing new was added to the cart.${reviewText}${skippedText}`);
      }
    },
    onError: (err) => toast.error("Could not confirm", toApiError(err).message),
  });

  const review = useMutation({
    mutationFn: () => prescriptionApi.requestReview(prescriptionId, reviewMessage.trim() || undefined),
    onSuccess: (updated) => {
      queryClient.setQueryData(["prescription", prescriptionId], updated);
      setReviewMessage("");
      toast.success("Review requested", "A pharmacist will look at this prescription.");
    },
    onError: (err) => toast.error("Could not request review", toApiError(err).message),
  });

  if (isLoading && !prescription) return <Spinner label="Loading prescription" />;
  if (isError || !prescription) return <EmptyState title="Prescription not found" action={<LinkButton to="/prescriptions">My prescriptions</LinkButton>} />;

  const confirmed = prescription.user_confirmation_status === "confirmed";
  const matchedCount = drafts.filter((d) => d.matched_medicine_id !== null && d.matched_medicine_id !== undefined).length;
  const includedCount = drafts.filter((d) => d.included).length + newItems.length;
  const unmatchedIncluded = drafts.filter((d) => d.included && !d.matched_medicine_id).length;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow={`Uploaded ${formatDateTime(prescription.created_at)}`}
        title={`Prescription #${prescription.id}`}
        description={`${humanise(prescription.document_type)} · ${prescription.page_count} page${prescription.page_count === 1 ? "" : "s"} · OCR ${prescription.ocr_engine ?? "unavailable"}${prescription.ocr_confidence !== null ? ` · confidence ${percent(prescription.ocr_confidence)}` : ""}`}
        actions={
          <>
            {confirmed ? <Badge tone="success">Confirmed by you</Badge> : <Badge tone="warning">Awaiting your review</Badge>}
            <VerificationBadge status={prescription.pharmacist_verification_status} />
          </>
        }
      />

      {prescription.show_handwriting_disclaimer && prescription.handwriting_disclaimer && (
        <Alert tone="warning" title="Handwritten prescription">{prescription.handwriting_disclaimer}</Alert>
      )}
      {!confirmed && prescription.items.length > 0 && (
        <p className="text-sm text-muted">
          {matchedCount} of {prescription.items.length} medicine{prescription.items.length === 1 ? "" : "s"} matched to the catalogue.
          Check each line against your paper copy, pick the right product where it asks, then confirm.
        </p>
      )}
      {prescription.items.length === 0 && (
        <Alert tone="warning" title="No medicines could be read from this page">
          {prescription.document_type === "handwritten"
            ? "Handwriting cannot be read reliably by the text recogniser. Add the medicines below with the search box, or upload a clearer, printed copy."
            : "Try a sharper, well-lit photo with the whole page visible, or add the medicines below with the search box."}
        </Alert>
      )}
      {prescription.pharmacist_verification_status === "rejected" && (
        <Alert tone="error" title="Rejected by the pharmacist">
          {prescription.verifications[0]?.notes ?? "This prescription cannot be used for prescription-only medicines."} You can upload a clearer copy.
        </Alert>
      )}
      {prescription.pharmacist_verification_status === "clarification_requested" && (
        <Alert tone="info" title="The pharmacist needs more information">
          {prescription.verifications[0]?.notes}. Update the details below and confirm again.
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">Medicines we read ({prescription.items.length})</h2>
            {editable && (
              <Button variant="outline" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setNewItems((n) => [...n, { key: Date.now(), extracted_name: "", matched_medicine_id: null }])}>
                Add medicine
              </Button>
            )}
          </div>

          {drafts.length === 0 && newItems.length === 0 && (
            <p className="rounded-2xl border border-dashed border-line bg-white px-4 py-6 text-center text-sm text-muted">
              Use “Add medicine” to enter the medicines from your prescription.
            </p>
          )}

          {drafts.map((draft) => (
            <div key={draft.item_id} className="space-y-2">
              <ItemEditor draft={draft} editable={editable} onChange={(next) => setDrafts((all) => all.map((d) => (d.item_id === next.item_id ? next : d)))} />
              {confirmed && draft.included && <AddToCartRow item={prescription.items.find((i) => i.id === draft.item_id)!} />}
            </div>
          ))}

          {newItems.map((item) => (
            <div key={item.key} className="rounded-2xl border border-brand-300 bg-white p-4 shadow-card">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-brand-700">New medicine (added by you)</p>
                <button type="button" onClick={() => setNewItems((n) => n.filter((x) => x.key !== item.key))} className="text-muted hover:text-rose-600" aria-label="Remove">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-3">
                <MedicinePicker
                  placeholder="Search the catalogue for the medicine"
                  onSelect={(m) =>
                    setNewItems((n) =>
                      n.map((x) =>
                        x.key === item.key
                          ? { ...x, matched_medicine_id: m.id, extracted_name: m.medicine_name, medicine_name: m.medicine_name, strength_text: m.strength ?? "" }
                          : x,
                      ),
                    )
                  }
                />
                {item.medicine_name && <p className="mt-1 text-xs text-emerald-700">Selected: {item.medicine_name}</p>}
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Input label="Name as written" value={item.extracted_name} onChange={(e) => setNewItems((n) => n.map((x) => (x.key === item.key ? { ...x, extracted_name: e.target.value } : x)))} required />
                <Input label="Strength" value={item.strength_text ?? ""} onChange={(e) => setNewItems((n) => n.map((x) => (x.key === item.key ? { ...x, strength_text: e.target.value } : x)))} />
                <Input label="Frequency" value={item.frequency_text ?? ""} onChange={(e) => setNewItems((n) => n.map((x) => (x.key === item.key ? { ...x, frequency_text: e.target.value } : x)))} />
              </div>
            </div>
          ))}

          {editable && (drafts.length > 0 || newItems.length > 0) && (
            <Card className="space-y-4">
              <Textarea label="Note for the pharmacist (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} placeholder="Anything that helps, e.g. the doctor's name or which line was hard to read." />
              <Checkbox
                label="Ask a pharmacist to review this prescription (optional)"
                description="Your order will wait for the pharmacist before it is processed."
                checked={requestReview}
                onChange={(e) => setRequestReview(e.target.checked)}
              />
              {unmatchedIncluded > 0 && (
                <Alert tone="warning">
                  {unmatchedIncluded} included medicine{unmatchedIncluded === 1 ? " has" : "s have"} no catalogue match. They will be kept on the prescription but cannot be added to the cart.
                </Alert>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-muted">
                  Confirming records that you checked these details against your prescription and adds one pack of each matched medicine to your cart.
                </p>
                <Button
                  size="lg"
                  loading={confirm.isPending}
                  disabled={includedCount === 0 || newItems.some((n) => !n.extracted_name.trim())}
                  leftIcon={<ShoppingCart className="h-5 w-5" />}
                  onClick={() => confirm.mutate()}
                >
                  {confirmed ? "Save and add to cart" : "Confirm and add to cart"}
                </Button>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card padded={false} className="overflow-hidden">
            <div className="border-b border-line px-4 py-3">
              <p className="text-sm font-semibold text-ink">Original document</p>
            </div>
            {sessionData?.preview_images.length ? (
              <div className="scrollbar-thin max-h-[420px] space-y-2 overflow-y-auto bg-surface p-2">
                {sessionData.preview_images.map((src, i) => (
                  <img key={i} src={src} alt={`Prescription page ${i + 1}`} className="w-full rounded-lg border border-line" />
                ))}
                <p className="px-1 pb-1 text-xs text-muted">Shown for this session only. The file is not stored.</p>
              </div>
            ) : (
              <p className="p-4 text-sm text-muted">
                The preview is only available during the upload session. Original images are never stored, so compare the details against your paper copy.
              </p>
            )}
          </Card>

          {prescription.items.length > 0 || sessionData?.extracted_text ? (
            <Card padded={false}>
              <button type="button" onClick={() => setShowText((s) => !s)} className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-ink">
                Text we extracted <ChevronDown className={cn("h-4 w-4 transition-transform", showText && "rotate-180")} />
              </button>
              {showText && (
                <pre className="scrollbar-thin max-h-72 overflow-auto whitespace-pre-wrap border-t border-line bg-surface px-4 py-3 font-mono text-xs text-ink">
                  {sessionData?.extracted_text || "Text is kept on the server for the pharmacist and is only shown here during the upload session."}
                </pre>
              )}
            </Card>
          ) : null}

          <Card>
            <p className="text-sm font-semibold text-ink">How it was read</p>
            <dl className="mt-2 space-y-1 text-xs text-muted">
              <div className="flex justify-between"><dt>Text recognition</dt><dd className="text-ink">{prescription.ocr_engine ?? "not available"}</dd></div>
              <div className="flex justify-between"><dt>Fields extracted by</dt><dd className="text-ink">{prescription.ai_review_status === "completed" ? `language model (${prescription.ai_model})` : prescription.ai_review_status === "skipped" ? "nothing to extract" : "simple rules"}</dd></div>
              <div className="flex justify-between"><dt>Source</dt><dd className="text-ink uppercase">{prescription.source_format}</dd></div>
              {sessionData && <div className="flex justify-between"><dt>Processing time</dt><dd className="text-ink">{(sessionData.processing.elapsed_ms / 1000).toFixed(1)} s</dd></div>}
            </dl>
            {sessionData && sessionData.processing.notes.length > 0 && (
              <ul className="mt-2 space-y-1 border-t border-line pt-2 text-xs text-muted">
                {sessionData.processing.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </Card>

          {confirmed && prescription.pharmacist_verification_status === "not_required" && (
            <Card className="space-y-2">
              <p className="text-sm font-semibold text-ink">Want a pharmacist to double-check?</p>
              <Textarea value={reviewMessage} onChange={(e) => setReviewMessage(e.target.value)} placeholder="Optional message" maxLength={1000} />
              <Button variant="secondary" size="sm" loading={review.isPending} onClick={() => review.mutate()}>Request review</Button>
            </Card>
          )}

          {prescription.verifications.length > 0 && (
            <Card>
              <p className="text-sm font-semibold text-ink">Pharmacist history</p>
              <ul className="mt-2 space-y-2 text-xs">
                {prescription.verifications.map((v) => (
                  <li key={v.id} className="rounded-lg bg-surface p-2">
                    <p className="font-semibold text-ink">{humanise(v.verification_status)} · {v.pharmacist_name ?? "Pharmacist"}</p>
                    <p className="text-muted">{formatDateTime(v.verified_at)}</p>
                    {v.notes && <p className="mt-1 text-ink">{v.notes}</p>}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <p className="text-xs text-muted">
            Need to order? Go to your <Link to="/cart" className="font-semibold text-brand-600 hover:underline">cart</Link> once the medicines are added.
          </p>
        </div>
      </div>
    </div>
  );
}

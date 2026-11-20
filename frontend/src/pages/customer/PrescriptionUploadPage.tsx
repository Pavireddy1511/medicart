import { FileText, ImageIcon, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Feedback";
import { Checkbox } from "@/components/ui/Form";
import { Card, PageHeader } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { prescriptionApi } from "@/services/api";
import { toApiError } from "@/services/http";
import { analysisStore } from "@/utils/analysisStore";
import { cn } from "@/utils/cn";

const MAX_MB = 10;
const ACCEPT = ["image/jpeg", "image/png", "application/pdf"];
const EXT = /\.(jpe?g|png|pdf)$/i;

type DocType = "" | "printed" | "handwritten";

const samples = [
  { label: "printed prescription", file: "sample-prescription-printed.png" },
  { label: "script-style prescription", file: "sample-prescription-script.jpg" },
];

export default function PrescriptionUploadPage() {
  useDocumentTitle("Upload prescription");
  const navigate = useNavigate();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const preview = useMemo(() => (file && file.type.startsWith("image/") ? URL.createObjectURL(file) : null), [file]);
  const [docType, setDocType] = useState<DocType>("");
  const [consent, setConsent] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [stage, setStage] = useState<"idle" | "uploading" | "processing">("idle");

  useEffect(() => {
    if (!preview) return;
    return () => URL.revokeObjectURL(preview);
  }, [preview]);

  const pick = (candidate: File | undefined) => {
    setError(null);
    if (!candidate) return;
    if (!ACCEPT.includes(candidate.type) && !EXT.test(candidate.name)) {
      setError("Only JPG, PNG and PDF files are supported.");
      return;
    }
    if (candidate.size > MAX_MB * 1024 * 1024) {
      setError(`The file is larger than ${MAX_MB} MB. Try a smaller image or compress the PDF.`);
      return;
    }
    if (candidate.size === 0) {
      setError("The selected file is empty.");
      return;
    }
    setFile(candidate);
  };

  const loadSample = async (sample: (typeof samples)[number]) => {
    setError(null);
    try {
      const blob = await fetch(`/samples/${sample.file}`).then((r) => {
        if (!r.ok) throw new Error("sample missing");
        return r.blob();
      });
      setFile(new File([blob], sample.file, { type: blob.type || "image/png" }));
    } catch {
      setError("The sample image could not be loaded.");
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files?.[0]);
  };

  const analyse = async () => {
    if (!file) return;
    setError(null);
    setStage("uploading");
    setProgress(0);
    try {
      const result = await prescriptionApi.analyse(file, docType || null, (pct) => {
        setProgress(pct);
        if (pct >= 100) setStage("processing");
      });
      analysisStore.set(result);
      navigate(`/prescriptions/${result.prescription.id}`, { replace: true });
    } catch (err) {
      const apiError = toApiError(err);
      setError(apiError.message);
      toast.error("Could not analyse the prescription", apiError.message);
    } finally {
      setStage("idle");
      setProgress(null);
    }
  };

  const busy = stage !== "idle";

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader title="Upload a prescription" description="JPG, PNG or PDF up to 10 MB. We read the text, you check it, a pharmacist verifies it." />

      <Card className="space-y-5">
        {!file ? (
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
              dragging ? "border-brand-500 bg-brand-50" : "border-brand-200 bg-surface hover:border-brand-400 hover:bg-brand-50",
            )}
          >
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-100 text-brand-600">
              <Upload className="h-6 w-6" />
            </span>
            <p className="mt-4 text-base font-semibold text-ink">Drag and drop your prescription here</p>
            <p className="mt-1 text-sm text-muted">or click to browse. JPG, PNG or PDF (first 3 pages are read).</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2 text-xs" onClick={(e) => e.stopPropagation()}>
              <span className="text-muted">No prescription handy? Try a fictional sample:</span>
              {samples.map((s) => (
                <button key={s.file} type="button" onClick={() => loadSample(s)} className="font-semibold text-brand-600 hover:underline">
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="flex h-56 w-full items-center justify-center overflow-hidden rounded-xl border border-line bg-surface sm:w-56">
              {preview ? (
                <img src={preview} alt="Prescription preview" className="h-full w-full object-contain" />
              ) : (
                <div className="flex flex-col items-center text-muted">
                  <FileText className="h-12 w-12" />
                  <span className="mt-2 text-xs font-medium">PDF document</span>
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-ink">{file.name}</p>
                  <p className="text-xs text-muted">
                    {(file.size / 1024 / 1024).toFixed(2)} MB · {file.type || "unknown type"}
                  </p>
                </div>
                <button type="button" onClick={() => setFile(null)} disabled={busy} className="rounded-lg p-1.5 text-muted hover:bg-brand-50 hover:text-ink" aria-label="Remove file">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <fieldset>
                <legend className="text-sm font-medium text-ink">What kind of prescription is this?</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(
                    [
                      ["", "Let the system decide"],
                      ["printed", "Printed"],
                      ["handwritten", "Handwritten"],
                    ] as [DocType, string][]
                  ).map(([value, label]) => (
                    <label
                      key={value}
                      className={cn(
                        "cursor-pointer rounded-full border px-3 py-1.5 text-sm",
                        docType === value ? "border-brand-500 bg-brand-50 text-brand-700" : "border-line text-ink hover:border-brand-300",
                      )}
                    >
                      <input type="radio" name="doctype" className="sr-only" checked={docType === value} onChange={() => setDocType(value)} />
                      {label}
                    </label>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-muted">Handwritten recognition is experimental and often wrong. Everything can be corrected on the next screen.</p>
              </fieldset>
            </div>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0])}
        />

        {error && <Alert tone="error">{error}</Alert>}

        <Checkbox
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          label="I understand how this works"
          description="The image is processed with OCR and a third-party AI service (Groq) to extract text for this session only. The original file is not stored. I will only upload prescriptions that belong to me or that I am allowed to share."
        />

        {progress !== null && (
          <div>
            <div className="flex justify-between text-xs text-muted">
              <span>{stage === "uploading" ? "Uploading" : "Reading the prescription (this can take up to a minute)"}</span>
              <span>{stage === "uploading" ? `${progress}%` : ""}</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-brand-100">
              <div className={cn("h-full rounded-full bg-brand-500 transition-all", stage === "processing" && "animate-pulse")} style={{ width: `${stage === "processing" ? 100 : progress}%` }} />
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <p className="inline-flex items-center gap-2 text-xs text-muted">
            <ImageIcon className="h-4 w-4" /> Tip: a flat, well-lit photo with the whole page visible reads best.
          </p>
          <Button size="lg" disabled={!file || !consent} loading={busy} onClick={analyse}>
            Analyse prescription
          </Button>
        </div>
      </Card>

      <Alert tone="info" title="What happens next">
        We show you every medicine we could read and the closest products in our catalogue. Fix anything that is wrong, then confirm:
        the matched medicines go straight into your cart. You can also ask a pharmacist to review the prescription.
      </Alert>
    </div>
  );
}

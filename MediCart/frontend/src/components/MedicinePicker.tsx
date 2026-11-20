import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Feedback";
import { inputClasses } from "@/components/ui/styles";
import { useDebounce } from "@/hooks/useUtilities";
import { catalogueApi } from "@/services/api";
import type { Medicine } from "@/types";

export function MedicinePicker({
  onSelect,
  placeholder = "Search the catalogue",
  autoFocus,
}: {
  onSelect: (medicine: Medicine) => void;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const debounced = useDebounce(term.trim(), 250);
  const ref = useRef<HTMLDivElement>(null);

  const { data, isFetching } = useQuery({
    queryKey: ["picker", debounced],
    queryFn: () => catalogueApi.search({ q: debounced, page_size: 8 }),
    enabled: debounced.length >= 2,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <input
        type="search"
        value={term}
        autoFocus={autoFocus}
        onChange={(e) => {
          setTerm(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        aria-label={placeholder}
        className={inputClasses(false, "pl-9")}
      />
      {open && debounced.length >= 2 && (
        <div className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-line bg-white p-1 shadow-pop">
          {isFetching && !data && <p className="px-3 py-2 text-sm text-muted">Searching…</p>}
          {data && data.items.length === 0 && <p className="px-3 py-2 text-sm text-muted">No catalogue match for “{debounced}”.</p>}
          {data?.items.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => {
                onSelect(m);
                setTerm("");
                setOpen(false);
              }}
              className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left hover:bg-brand-50"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{m.medicine_name}</span>
                <span className="block truncate text-xs text-muted">
                  {[m.brand_name, m.generic_name, m.strength, m.formulation].filter(Boolean).join(" · ")}
                </span>
              </span>
              {m.prescription_required && <Badge tone="warning">Rx</Badge>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { ProductCard } from "@/components/ui/Commerce";
import { EmptyState, Skeleton } from "@/components/ui/Feedback";
import { Checkbox, Input, Select } from "@/components/ui/Form";
import { Pagination } from "@/components/ui/Layout";
import { useCart } from "@/hooks/useCart";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { catalogueApi } from "@/services/api";
import type { MedicineQuery, SortOption } from "@/types";
import { cn } from "@/utils/cn";

const sortOptions: { value: SortOption; label: string }[] = [
  { value: "relevance", label: "Relevance" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "name_asc", label: "Name: A to Z" },
  { value: "name_desc", label: "Name: Z to A" },
  { value: "newest", label: "Newest" },
];

function readQuery(params: URLSearchParams): MedicineQuery {
  const num = (key: string) => {
    const v = params.get(key);
    return v !== null && v !== "" && !Number.isNaN(Number(v)) ? Number(v) : undefined;
  };
  const bool = (key: string) => (params.has(key) ? params.get(key) === "true" : undefined);
  return {
    q: params.get("q") || undefined,
    category: params.get("category") || undefined,
    min_price: num("min_price"),
    max_price: num("max_price"),
    in_stock: bool("in_stock"),
    prescription_required: bool("prescription_required"),
    sort: (params.get("sort") as SortOption) || "relevance",
    page: num("page") ?? 1,
    page_size: 24,
  };
}

export default function CataloguePage() {
  const [params, setParams] = useSearchParams();
  const query = readQuery(params);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const { add } = useCart();

  useDocumentTitle(query.q ? `Search: ${query.q}` : "Catalogue");

  const { data: categories } = useQuery({ queryKey: ["categories"], queryFn: catalogueApi.categories, staleTime: 5 * 60_000 });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["medicines", query],
    queryFn: () => catalogueApi.search(query),
    placeholderData: (previous) => previous,
  });

  const update = (changes: Record<string, string | number | boolean | undefined>, resetPage = true) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => {
      if (value === undefined || value === "" || value === false) next.delete(key);
      else next.set(key, String(value));
    });
    if (resetPage) next.delete("page");
    setParams(next);
  };

  const activeCategory = categories?.find((c) => c.slug === query.category);
  const activeFilters = [
    query.category && activeCategory?.name,
    query.min_price !== undefined && `Min ₹${query.min_price}`,
    query.max_price !== undefined && `Max ₹${query.max_price}`,
    query.in_stock && "In stock",
    query.prescription_required === true && "Prescription only",
    query.prescription_required === false && "No prescription",
  ].filter(Boolean) as string[];

  const filters = (
    <div className="space-y-5">
      <Select
        label="Category"
        value={query.category ?? ""}
        placeholder="All categories"
        options={(categories ?? []).map((c) => ({ value: c.slug, label: `${c.name} (${c.medicine_count})` }))}
        onChange={(e) => update({ category: e.target.value || undefined })}
      />
      <div>
        <p className="mb-1.5 text-sm font-medium text-ink">Price range (₹)</p>
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            min={0}
            placeholder="Min"
            aria-label="Minimum price"
            defaultValue={query.min_price ?? ""}
            onBlur={(e) => update({ min_price: e.target.value || undefined })}
          />
          <Input
            type="number"
            min={0}
            placeholder="Max"
            aria-label="Maximum price"
            defaultValue={query.max_price ?? ""}
            onBlur={(e) => update({ max_price: e.target.value || undefined })}
          />
        </div>
      </div>
      <div className="space-y-3">
        <Checkbox label="In stock only" checked={Boolean(query.in_stock)} onChange={(e) => update({ in_stock: e.target.checked || undefined })} />
        <Select
          label="Prescription"
          value={query.prescription_required === undefined ? "" : String(query.prescription_required)}
          placeholder="Any"
          options={[
            { value: "false", label: "No prescription needed" },
            { value: "true", label: "Prescription required" },
          ]}
          onChange={(e) => update({ prescription_required: e.target.value || undefined })}
        />
      </div>
      {activeFilters.length > 0 && (
        <Button variant="ghost" size="sm" onClick={() => setParams(query.q ? { q: query.q } : {})}>
          Clear filters
        </Button>
      )}
    </div>
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">
            {query.q ? `Results for “${query.q}”` : activeCategory?.name ?? "All products"}
          </h1>
          <p className="text-sm text-muted">
            {activeCategory?.description ?? (data ? `${data.total} products` : "Browse medicines and health essentials")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="lg:hidden" leftIcon={<SlidersHorizontal className="h-4 w-4" />} onClick={() => setFiltersOpen(true)}>
            Filters{activeFilters.length ? ` (${activeFilters.length})` : ""}
          </Button>
          <Select
            aria-label="Sort by"
            value={query.sort}
            options={sortOptions}
            onChange={(e) => update({ sort: e.target.value }, false)}
            className="w-48"
          />
        </div>
      </div>

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {activeFilters.map((f) => (
            <span key={f} className="rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold text-brand-700">
              {f}
            </span>
          ))}
          <button type="button" onClick={() => setParams(query.q ? { q: query.q } : {})} className="inline-flex items-center gap-1 text-xs font-semibold text-muted hover:text-ink">
            <X className="h-3.5 w-3.5" /> Clear all
          </button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-2xl border border-line bg-white p-4 shadow-card">
            <p className="mb-3 text-sm font-semibold text-ink">Filters</p>
            {filters}
          </div>
        </aside>

        <div className="space-y-5">
          {isLoading && !data ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="aspect-[3/4]" />
              ))}
            </div>
          ) : isError ? (
            <EmptyState title="Could not load products" description="Please try again in a moment." />
          ) : data && data.items.length === 0 ? (
            <EmptyState
              title="No products found"
              description={query.q ? "Try a different spelling, the generic name, or fewer filters." : "No products match these filters."}
              action={
                <Button variant="outline" onClick={() => setParams({})}>
                  Clear search
                </Button>
              }
            />
          ) : (
            <div className={cn("grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4", isLoading && "opacity-60")}>
              {data?.items.map((m) => (
                <ProductCard key={m.id} medicine={m} onAdd={(productId) => add.mutate({ productId })} adding={add.isPending} />
              ))}
            </div>
          )}
          {data && <Pagination page={data.page} pages={data.pages} total={data.total} onChange={(page) => update({ page }, false)} />}
        </div>
      </div>

      {filtersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setFiltersOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-white p-5 shadow-pop">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-base font-semibold">Filters</p>
              <button type="button" onClick={() => setFiltersOpen(false)} className="rounded-lg p-1.5 hover:bg-brand-50" aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </div>
            {filters}
            <Button fullWidth className="mt-5" onClick={() => setFiltersOpen(false)}>
              Show results{data ? ` (${data.total})` : ""}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

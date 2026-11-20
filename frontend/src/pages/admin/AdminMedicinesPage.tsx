import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, LinkButton } from "@/components/ui/Button";
import { Badge, EmptyState, Spinner } from "@/components/ui/Feedback";
import { Input, Select } from "@/components/ui/Form";
import { ConfirmDialog, PageHeader, Pagination, Table, td, th } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDebounce, useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { AdminMedicine } from "@/types";
import { formatPrice } from "@/utils/format";

export default function AdminMedicinesPage() {
  useDocumentTitle("Medicines");
  const queryClient = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<AdminMedicine | null>(null);
  const search = useDebounce(q.trim(), 300);

  const categories = useQuery({ queryKey: ["admin", "categories"], queryFn: adminApi.categories });
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "medicines", search, categoryId, page],
    queryFn: () => adminApi.medicines({ q: search || undefined, category_id: categoryId ? Number(categoryId) : undefined, page, page_size: 20 }),
    placeholderData: (prev) => prev,
  });

  const remove = useMutation({
    mutationFn: (id: number) => adminApi.deleteMedicine(id),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      queryClient.invalidateQueries({ queryKey: ["home"] });
      setDeleting(null);
      toast.success(result.message);
    },
    onError: (err) => toast.error("Could not delete", toApiError(err).message),
  });

  const categoryName = (id: number | null) => categories.data?.find((c) => c.id === id)?.name ?? "-";

  return (
    <div className="space-y-5">
      <PageHeader title="Medicines & stock" description="Catalogue, pack sizes, prices and inventory." actions={<LinkButton to="/admin/medicines/new" leftIcon={<Plus className="h-4 w-4" />}>Add medicine</LinkButton>} />
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input placeholder="Search name, brand, generic or manufacturer" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} leftIcon={<Search className="h-4 w-4" />} className="flex-1" />
        <Select
          value={categoryId}
          placeholder="All categories"
          options={(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
          onChange={(e) => { setCategoryId(e.target.value); setPage(1); }}
          className="sm:w-56"
        />
      </div>

      {isLoading && !data ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No medicines found" action={<LinkButton to="/admin/medicines/new">Add the first medicine</LinkButton>} />
      ) : (
        <>
          <Table>
            <thead className="bg-surface">
              <tr>
                <th className={th}>Medicine</th>
                <th className={th}>Category</th>
                <th className={th}>Packs & price</th>
                <th className={th}>Stock</th>
                <th className={th}>Status</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.items.map((m) => {
                const stock = m.products.reduce((sum, p) => sum + p.available_quantity, 0);
                return (
                  <tr key={m.id} className="hover:bg-brand-50/40">
                    <td className={td}>
                      <Link to={`/admin/medicines/${m.id}`} className="font-semibold text-ink hover:text-brand-600">{m.medicine_name}</Link>
                      <p className="text-xs text-muted">{[m.brand_name, m.strength, m.formulation, m.manufacturer].filter(Boolean).join(" · ")}</p>
                    </td>
                    <td className={`${td} text-xs`}>{categoryName(m.category_id)}</td>
                    <td className={`${td} text-xs`}>
                      {m.products.map((p) => (
                        <p key={p.id}>
                          {p.pack_size} · {formatPrice(p.price)}
                          {p.discount_percent > 0 && <span className="text-emerald-600"> (-{p.discount_percent}%)</span>}
                          {!p.is_active && <span className="text-muted"> · inactive</span>}
                        </p>
                      ))}
                    </td>
                    <td className={td}>
                      <span className={`font-semibold ${stock === 0 ? "text-rose-600" : stock <= 10 ? "text-amber-600" : "text-ink"}`}>{stock}</span>
                    </td>
                    <td className={td}>
                      <div className="flex flex-wrap gap-1">
                        {m.is_active ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Inactive</Badge>}
                        {m.prescription_required && <Badge tone="warning">Rx</Badge>}
                      </div>
                    </td>
                    <td className={`${td} text-right`}>
                      <div className="flex justify-end gap-1">
                        <LinkButton to={`/admin/medicines/${m.id}`} variant="ghost" size="sm" leftIcon={<Pencil className="h-3.5 w-3.5" />}>Edit</LinkButton>
                        <Button variant="ghost" size="sm" className="text-rose-600 hover:bg-rose-50" leftIcon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setDeleting(m)}>Delete</Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
        </>
      )}

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
        loading={remove.isPending}
        title={`Delete ${deleting?.medicine_name}?`}
        description="If the medicine appears in past orders it is deactivated instead of deleted, so order history stays intact."
        confirmLabel="Delete"
        tone="danger"
      />
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { CategoryIcon } from "@/components/ui/Commerce";
import { Badge, Spinner } from "@/components/ui/Feedback";
import { Checkbox, Input, Select } from "@/components/ui/Form";
import { ConfirmDialog, Modal, PageHeader, Table, td, th } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { AdminCategory } from "@/types";
import { categoryIcons } from "@/utils/catalogue";

type Form = { name: string; slug: string; description: string; icon: string; sort_order: number; is_active: boolean };
const empty: Form = { name: "", slug: "", description: "", icon: "pill", sort_order: 0, is_active: true };

export default function AdminCategoriesPage() {
  useDocumentTitle("Categories");
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<AdminCategory | "new" | null>(null);
  const [form, setForm] = useState<Form>(empty);
  const [deleting, setDeleting] = useState<AdminCategory | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["admin", "categories"], queryFn: adminApi.categories });
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin", "categories"] });
    queryClient.invalidateQueries({ queryKey: ["home"] });
    queryClient.invalidateQueries({ queryKey: ["categories"] });
  };

  const save = useMutation({
    mutationFn: () => {
      const payload = { ...form, slug: form.slug.trim() || undefined, description: form.description.trim() || null };
      return editing === "new" || !editing ? adminApi.createCategory(payload) : adminApi.updateCategory(editing.id, payload);
    },
    onSuccess: () => {
      invalidate();
      setEditing(null);
      toast.success("Category saved");
    },
    onError: (err) => setError(toApiError(err).message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => adminApi.deleteCategory(id),
    onSuccess: () => {
      invalidate();
      setDeleting(null);
      toast.success("Category deleted");
    },
    onError: (err) => {
      setDeleting(null);
      toast.error("Could not delete", toApiError(err).message);
    },
  });

  const open = (target: AdminCategory | "new") => {
    setError(null);
    setForm(target === "new" ? empty : { name: target.name, slug: target.slug, description: target.description ?? "", icon: target.icon ?? "pill", sort_order: target.sort_order, is_active: target.is_active });
    setEditing(target);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (form.name.trim().length < 2) {
      setError("Enter a category name");
      return;
    }
    save.mutate();
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Categories" description="The storefront sidebar shows active categories in this order." actions={<Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => open("new")}>Add category</Button>} />
      {isLoading ? (
        <Spinner />
      ) : (
        <Table>
          <thead className="bg-surface">
            <tr>
              <th className={th}>Category</th>
              <th className={th}>Slug</th>
              <th className={th}>Medicines</th>
              <th className={th}>Order</th>
              <th className={th}>Status</th>
              <th className={th}></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(data ?? []).map((c) => (
              <tr key={c.id}>
                <td className={td}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-100 text-brand-600"><CategoryIcon icon={c.icon} className="h-4 w-4" /></span>
                    <div>
                      <p className="font-semibold">{c.name}</p>
                      <p className="text-xs text-muted">{c.description}</p>
                    </div>
                  </div>
                </td>
                <td className={`${td} font-mono text-xs`}>{c.slug}</td>
                <td className={td}>{c.medicine_count}</td>
                <td className={td}>{c.sort_order}</td>
                <td className={td}>{c.is_active ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Hidden</Badge>}</td>
                <td className={`${td} text-right`}>
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" leftIcon={<Pencil className="h-3.5 w-3.5" />} onClick={() => open(c)}>Edit</Button>
                    <Button variant="ghost" size="sm" className="text-rose-600 hover:bg-rose-50" leftIcon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setDeleting(c)} disabled={c.medicine_count > 0}>Delete</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "Add category" : "Edit category"}>
        <form onSubmit={submit} className="space-y-4" noValidate id="category-form">
          {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
          <Input label="Name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
          <Input label="Slug" hint="Used in the URL. Leave blank to generate from the name." value={form.slug} onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))} />
          <Input label="Description" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Icon" value={form.icon} options={Object.keys(categoryIcons).map((k) => ({ value: k, label: k }))} onChange={(e) => setForm((f) => ({ ...f, icon: e.target.value }))} />
            <Input label="Sort order" type="number" value={form.sort_order} onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))} />
          </div>
          <Checkbox label="Visible on the storefront" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button type="submit" loading={save.isPending}>Save</Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={deleting !== null} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting.id)} loading={remove.isPending} title={`Delete ${deleting?.name}?`} description="Only empty categories can be deleted." confirmLabel="Delete" tone="danger" />
    </div>
  );
}

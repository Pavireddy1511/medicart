import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Alert, Badge, Spinner } from "@/components/ui/Feedback";
import { Checkbox, Input, Select, Textarea } from "@/components/ui/Form";
import { Card, Modal, PageHeader, Table, td, th } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { AdminMedicine, AdminProduct, MedicineInput, ProductInput } from "@/types";
import { formatPrice } from "@/utils/format";

const emptyMedicine: MedicineInput = {
  medicine_name: "",
  generic_name: "",
  brand_name: "",
  strength: "",
  formulation: "",
  manufacturer: "",
  description: "",
  prescription_required: false,
  category_id: null,
  image_url: "",
  is_active: true,
};

const emptyProduct: ProductInput = { pack_size: "", mrp: 0, price: 0, is_active: true, available_quantity: 0, batch_number: "", expiry_date: "" };

function clean(data: MedicineInput): MedicineInput {
  const out = { ...data };
  (["generic_name", "brand_name", "strength", "formulation", "manufacturer", "description", "image_url"] as const).forEach((k) => {
    if (!out[k]) out[k] = null;
  });
  return out;
}

function cleanProduct(p: ProductInput): ProductInput {
  return { ...p, sku: p.sku?.trim() || null, batch_number: p.batch_number?.trim() || null, expiry_date: p.expiry_date || null, mrp: Number(p.mrp), price: Number(p.price), available_quantity: Number(p.available_quantity) };
}

function ProductFields({ value, onChange, errors = {} }: { value: ProductInput; onChange: (next: ProductInput) => void; errors?: Record<string, string> }) {
  const set = (key: keyof ProductInput, v: string | number | boolean) => onChange({ ...value, [key]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Input label="Pack size" placeholder="Strip of 10 tablets" value={value.pack_size} onChange={(e) => set("pack_size", e.target.value)} error={errors.pack_size} required />
      <Input label="MRP (₹)" type="number" min={0.01} step="0.01" value={value.mrp || ""} onChange={(e) => set("mrp", e.target.value === "" ? 0 : Number(e.target.value))} error={errors.mrp} required />
      <Input label="Selling price (₹)" type="number" min={0.01} step="0.01" value={value.price || ""} onChange={(e) => set("price", e.target.value === "" ? 0 : Number(e.target.value))} error={errors.price} required />
      <Input label="Stock quantity" type="number" min={0} value={value.available_quantity} onChange={(e) => set("available_quantity", Number(e.target.value))} error={errors.available_quantity} />
      <Input label="Batch number" hint="Demo data" value={value.batch_number ?? ""} onChange={(e) => set("batch_number", e.target.value)} />
      <Input label="Expiry date" type="date" value={value.expiry_date ?? ""} onChange={(e) => set("expiry_date", e.target.value)} />
    </div>
  );
}

export default function AdminMedicineFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const medicineId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  useDocumentTitle(isEdit ? "Edit medicine" : "Add medicine");

  const [form, setForm] = useState<MedicineInput>(emptyMedicine);
  const [products, setProducts] = useState<ProductInput[]>([{ ...emptyProduct }]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [productModal, setProductModal] = useState<null | { mode: "add" } | { mode: "edit"; product: AdminProduct } | { mode: "stock"; product: AdminProduct }>(null);
  const [modalProduct, setModalProduct] = useState<ProductInput>(emptyProduct);

  const categories = useQuery({ queryKey: ["admin", "categories"], queryFn: adminApi.categories });
  const medicine = useQuery({ queryKey: ["admin", "medicine", medicineId], queryFn: () => adminApi.medicine(medicineId), enabled: isEdit });

  // Seed the form from the loaded record (and again after a save returns fresh data).
  const [loadedFrom, setLoadedFrom] = useState<AdminMedicine | null>(null);
  if (medicine.data && medicine.data !== loadedFrom) {
    const m = medicine.data;
    setLoadedFrom(m);
    setForm({
      medicine_name: m.medicine_name,
      generic_name: m.generic_name ?? "",
      brand_name: m.brand_name ?? "",
      strength: m.strength ?? "",
      formulation: m.formulation ?? "",
      manufacturer: m.manufacturer ?? "",
      description: m.description ?? "",
      prescription_required: m.prescription_required,
      category_id: m.category_id,
      image_url: m.image_url ?? "",
      is_active: m.is_active,
    });
  }

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin"] });
    queryClient.invalidateQueries({ queryKey: ["home"] });
    queryClient.invalidateQueries({ queryKey: ["medicines"] });
  };

  const save = useMutation({
    mutationFn: () =>
      isEdit ? adminApi.updateMedicine(medicineId, clean(form)) : adminApi.createMedicine({ ...clean(form), products: products.map(cleanProduct) }),
    onSuccess: (saved) => {
      invalidate();
      toast.success(isEdit ? "Medicine updated" : "Medicine created");
      if (!isEdit) navigate(`/admin/medicines/${saved.id}`, { replace: true });
    },
    onError: (err) => {
      const apiError = toApiError(err);
      setErrors(apiError.fieldErrors);
      setError(Object.keys(apiError.fieldErrors).length ? null : apiError.message);
    },
  });

  const productMutation = useMutation({
    mutationFn: async () => {
      if (!productModal) return;
      const data = cleanProduct(modalProduct);
      if (productModal.mode === "add") return adminApi.addProduct(medicineId, data);
      if (productModal.mode === "edit") return adminApi.updateProduct(productModal.product.id, { pack_size: data.pack_size, mrp: data.mrp, price: data.price, is_active: data.is_active });
      return adminApi.updateInventory(productModal.product.id, { available_quantity: data.available_quantity, batch_number: data.batch_number, expiry_date: data.expiry_date });
    },
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["admin", "medicine", medicineId] });
      setProductModal(null);
      toast.success("Saved");
    },
    onError: (err) => toast.error("Could not save", toApiError(err).message),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const local: Record<string, string> = {};
    if (form.medicine_name.trim().length < 2) local.medicine_name = "Enter the medicine name";
    if (!isEdit) {
      products.forEach((p, i) => {
        if (!p.pack_size.trim()) local[`products.${i}.pack_size`] = "Required";
        if (!(Number(p.mrp) > 0)) local[`products.${i}.mrp`] = "Enter the MRP";
        if (!(Number(p.price) > 0)) local[`products.${i}.price`] = "Enter the price";
        if (Number(p.price) > Number(p.mrp)) local[`products.${i}.price`] = "Price cannot exceed MRP";
      });
    }
    setErrors(local);
    if (Object.keys(local).length) return;
    save.mutate();
  };

  const openProductModal = (modal: typeof productModal) => {
    if (!modal) return;
    if (modal.mode === "add") setModalProduct({ ...emptyProduct });
    else
      setModalProduct({
        pack_size: modal.product.pack_size,
        mrp: modal.product.mrp,
        price: modal.product.price,
        is_active: modal.product.is_active,
        available_quantity: modal.product.inventory?.available_quantity ?? modal.product.available_quantity,
        batch_number: modal.product.inventory?.batch_number ?? "",
        expiry_date: modal.product.inventory?.expiry_date ?? "",
      });
    setProductModal(modal);
  };

  if (isEdit && medicine.isLoading) return <Spinner />;

  const set = (key: keyof MedicineInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <div className="space-y-5">
      <Link to="/admin/medicines" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Back to medicines</Link>
      <PageHeader title={isEdit ? `Edit ${medicine.data?.medicine_name ?? "medicine"}` : "Add a medicine"} description={isEdit ? "Changes apply to the storefront immediately." : "Create the medicine with at least one pack size."} />
      {error && <Alert tone="error">{error}</Alert>}

      <form onSubmit={submit} className="space-y-5" noValidate>
        <Card className="space-y-4">
          <h2 className="text-base font-semibold text-ink">Medicine details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Medicine name" value={form.medicine_name} onChange={set("medicine_name")} error={errors.medicine_name} required className="sm:col-span-2" />
            <Input label="Brand name" value={form.brand_name ?? ""} onChange={set("brand_name")} />
            <Input label="Generic name" value={form.generic_name ?? ""} onChange={set("generic_name")} />
            <Input label="Strength" placeholder="500 mg" value={form.strength ?? ""} onChange={set("strength")} />
            <Input label="Formulation" placeholder="tablet, syrup, cream…" value={form.formulation ?? ""} onChange={set("formulation")} />
            <Input label="Manufacturer" value={form.manufacturer ?? ""} onChange={set("manufacturer")} />
            <Select
              label="Category"
              value={form.category_id ? String(form.category_id) : ""}
              placeholder="No category"
              options={(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
              onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value ? Number(e.target.value) : null }))}
            />
            <Input label="Image URL" hint="Optional. Leave empty to use the category placeholder." value={form.image_url ?? ""} onChange={set("image_url")} className="sm:col-span-2" />
            <Textarea label="Description" value={form.description ?? ""} onChange={set("description")} className="sm:col-span-2" />
          </div>
          <div className="flex flex-wrap gap-6">
            <Checkbox label="Prescription required" description="Customers must have a pharmacist-approved prescription to order." checked={form.prescription_required} onChange={(e) => setForm((f) => ({ ...f, prescription_required: e.target.checked }))} />
            <Checkbox label="Active" description="Inactive medicines are hidden from the storefront." checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
          </div>
        </Card>

        {!isEdit && (
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">Pack sizes</h2>
              <Button type="button" variant="outline" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setProducts((p) => [...p, { ...emptyProduct }])}>Add pack</Button>
            </div>
            {products.map((p, i) => (
              <div key={i} className="rounded-xl border border-line p-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-semibold text-ink">Pack {i + 1}</p>
                  {products.length > 1 && (
                    <button type="button" className="text-muted hover:text-rose-600" onClick={() => setProducts((all) => all.filter((_, j) => j !== i))} aria-label="Remove pack"><Trash2 className="h-4 w-4" /></button>
                  )}
                </div>
                <ProductFields
                  value={p}
                  onChange={(next) => setProducts((all) => all.map((x, j) => (j === i ? next : x)))}
                  errors={Object.fromEntries(Object.entries(errors).filter(([k]) => k.startsWith(`products.${i}.`)).map(([k, v]) => [k.split(".")[2], v]))}
                />
              </div>
            ))}
          </Card>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate("/admin/medicines")}>Cancel</Button>
          <Button type="submit" loading={save.isPending}>{isEdit ? "Save changes" : "Create medicine"}</Button>
        </div>
      </form>

      {isEdit && medicine.data && (
        <Card padded={false}>
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="text-base font-semibold text-ink">Pack sizes & inventory</h2>
            <Button variant="outline" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => openProductModal({ mode: "add" })}>Add pack</Button>
          </div>
          <Table className="rounded-none border-0 shadow-none">
            <thead className="bg-surface">
              <tr>
                <th className={th}>SKU</th>
                <th className={th}>Pack</th>
                <th className={th}>MRP</th>
                <th className={th}>Price</th>
                <th className={th}>Stock</th>
                <th className={th}>Batch / expiry</th>
                <th className={th}>Status</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {medicine.data.products.map((p) => (
                <tr key={p.id}>
                  <td className={`${td} font-mono text-xs`}>{p.sku}</td>
                  <td className={td}>{p.pack_size}</td>
                  <td className={td}>{formatPrice(p.mrp)}</td>
                  <td className={td}>{formatPrice(p.price)}{p.discount_percent > 0 && <span className="ml-1 text-xs text-emerald-600">-{p.discount_percent}%</span>}</td>
                  <td className={`${td} font-semibold ${p.available_quantity === 0 ? "text-rose-600" : ""}`}>{p.available_quantity}</td>
                  <td className={`${td} text-xs text-muted`}>{p.inventory?.batch_number ?? "-"}<br />{p.inventory?.expiry_date ?? "-"}</td>
                  <td className={td}>{p.is_active ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Inactive</Badge>}</td>
                  <td className={`${td} text-right`}>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openProductModal({ mode: "stock", product: p })}>Stock</Button>
                      <Button variant="ghost" size="sm" onClick={() => openProductModal({ mode: "edit", product: p })}>Edit</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      <Modal
        open={productModal !== null}
        onClose={() => setProductModal(null)}
        title={productModal?.mode === "add" ? "Add pack size" : productModal?.mode === "edit" ? "Edit pack" : "Update stock"}
        size="lg"
        footer={
          <>
            <Button variant="outline" onClick={() => setProductModal(null)}>Cancel</Button>
            <Button loading={productMutation.isPending} onClick={() => productMutation.mutate()}>Save</Button>
          </>
        }
      >
        {productModal?.mode === "stock" ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="Available quantity" type="number" min={0} value={modalProduct.available_quantity} onChange={(e) => setModalProduct((p) => ({ ...p, available_quantity: Number(e.target.value) }))} />
            <Input label="Batch number" value={modalProduct.batch_number ?? ""} onChange={(e) => setModalProduct((p) => ({ ...p, batch_number: e.target.value }))} />
            <Input label="Expiry date" type="date" value={modalProduct.expiry_date ?? ""} onChange={(e) => setModalProduct((p) => ({ ...p, expiry_date: e.target.value }))} />
          </div>
        ) : (
          <div className="space-y-4">
            <ProductFields value={modalProduct} onChange={setModalProduct} />
            {productModal?.mode === "edit" && (
              <Checkbox label="Active" checked={modalProduct.is_active} onChange={(e) => setModalProduct((p) => ({ ...p, is_active: e.target.checked }))} />
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

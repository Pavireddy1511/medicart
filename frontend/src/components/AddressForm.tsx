import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Feedback";
import { Checkbox, Input, Select } from "@/components/ui/Form";
import { toApiError } from "@/services/http";
import type { Address, AddressInput } from "@/types";

const empty: AddressInput = {
  recipient_name: "",
  mobile_number: "",
  house_building: "",
  street: "",
  landmark: "",
  city: "",
  state: "",
  pincode: "",
  address_type: "home",
  is_default: false,
};

export function AddressForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel = "Save address",
}: {
  initial?: Address | null;
  onSubmit: (data: AddressInput) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const [form, setForm] = useState<AddressInput>(
    initial
      ? {
          recipient_name: initial.recipient_name,
          mobile_number: initial.mobile_number,
          house_building: initial.house_building,
          street: initial.street,
          landmark: initial.landmark ?? "",
          city: initial.city,
          state: initial.state,
          pincode: initial.pincode,
          address_type: initial.address_type,
          is_default: initial.is_default,
        }
      : empty,
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (key: keyof AddressInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    if (form.recipient_name.trim().length < 2) local.recipient_name = "Enter the recipient's name";
    if (!/^[6-9]\d{9}$/.test(form.mobile_number.replace(/\D/g, "").slice(-10))) local.mobile_number = "Enter a valid 10-digit mobile number";
    if (!form.house_building.trim()) local.house_building = "Required";
    if (!form.street.trim()) local.street = "Required";
    if (!form.city.trim()) local.city = "Required";
    if (!form.state.trim()) local.state = "Required";
    if (!/^[1-9]\d{5}$/.test(form.pincode.trim())) local.pincode = "Enter a valid 6-digit PIN code";
    setErrors(local);
    if (Object.keys(local).length) return;
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ ...form, landmark: form.landmark?.trim() || null });
    } catch (err) {
      const apiError = toApiError(err);
      setErrors(apiError.fieldErrors);
      if (!Object.keys(apiError.fieldErrors).length) setError(apiError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Recipient name" value={form.recipient_name} onChange={set("recipient_name")} error={errors.recipient_name} required />
        <Input label="Mobile number" type="tel" inputMode="numeric" value={form.mobile_number} onChange={set("mobile_number")} error={errors.mobile_number} required />
      </div>
      <Input label="House / flat / building" value={form.house_building} onChange={set("house_building")} error={errors.house_building} required />
      <Input label="Street / area" value={form.street} onChange={set("street")} error={errors.street} required />
      <Input label="Landmark" hint="Optional" value={form.landmark ?? ""} onChange={set("landmark")} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Input label="City" value={form.city} onChange={set("city")} error={errors.city} required />
        <Input label="State" value={form.state} onChange={set("state")} error={errors.state} required />
        <Input label="PIN code" inputMode="numeric" maxLength={6} value={form.pincode} onChange={set("pincode")} error={errors.pincode} required />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 sm:items-end">
        <Select
          label="Address type"
          value={form.address_type}
          onChange={set("address_type")}
          options={[
            { value: "home", label: "Home" },
            { value: "work", label: "Work" },
            { value: "other", label: "Other" },
          ]}
        />
        <Checkbox label="Set as default address" checked={form.is_default} onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))} />
      </div>
      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={saving}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

export function AddressText({ address, className }: { address: Omit<Address, "id" | "created_at" | "is_default">; className?: string }) {
  return (
    <p className={className}>
      <span className="font-semibold text-ink">{address.recipient_name}</span>
      <span className="block text-muted">
        {address.house_building}, {address.street}
        {address.landmark ? `, ${address.landmark}` : ""}
      </span>
      <span className="block text-muted">
        {address.city}, {address.state} {address.pincode}
      </span>
      <span className="block text-muted">+91 {address.mobile_number}</span>
    </p>
  );
}

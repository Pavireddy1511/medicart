import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, CreditCard, FileUp, MapPin, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AddressForm, AddressText } from "@/components/AddressForm";
import { Button, LinkButton } from "@/components/ui/Button";
import { Alert, Badge, EmptyState, Spinner, VerificationBadge } from "@/components/ui/Feedback";
import { Card, Modal, PageHeader } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { CART_KEY, useCart } from "@/hooks/useCart";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { addressApi, orderApi, prescriptionApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { AddressInput, PaymentMethod } from "@/types";
import { cn } from "@/utils/cn";
import { formatDate, formatPrice } from "@/utils/format";

export default function CheckoutPage() {
  useDocumentTitle("Checkout");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { cart, isLoading } = useCart();

  const [addressId, setAddressId] = useState<number | null>(null);
  const [payment, setPayment] = useState<PaymentMethod>("cod");
  const [prescriptionId, setPrescriptionId] = useState<number | null>(null);
  const [addingAddress, setAddingAddress] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addresses = useQuery({ queryKey: ["addresses"], queryFn: addressApi.list });
  const prescriptions = useQuery({
    queryKey: ["prescriptions"],
    queryFn: prescriptionApi.list,
    enabled: Boolean(cart?.requires_prescription),
  });

  const selectedAddressId =
    addressId ?? (addresses.data?.find((a) => a.is_default) ?? addresses.data?.[0])?.id ?? null;

  const usable = (prescriptions.data ?? []).filter(
    (p) => p.user_confirmation_status === "confirmed" && p.pharmacist_verification_status !== "rejected",
  );
  const selectedPrescriptionId = prescriptionId ?? usable[0]?.id ?? null;

  const createAddress = useMutation({
    mutationFn: (data: AddressInput) => addressApi.create(data),
    onSuccess: (address) => {
      queryClient.invalidateQueries({ queryKey: ["addresses"] });
      setAddressId(address.id);
      setAddingAddress(false);
    },
  });

  const place = useMutation({
    mutationFn: () =>
      orderApi.place({ address_id: selectedAddressId!, payment_method: payment, prescription_id: selectedPrescriptionId ?? undefined }),
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: CART_KEY });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      navigate(`/orders/${order.id}/success`, { replace: true });
    },
    onError: (err) => {
      const apiError = toApiError(err);
      setError(apiError.message);
      if (apiError.code === "insufficient_stock" || apiError.code === "product_unavailable") {
        queryClient.invalidateQueries({ queryKey: CART_KEY });
      }
      toast.error("Could not place the order", apiError.message);
    },
  });

  if (isLoading || !cart) return <Spinner label="Preparing checkout" />;
  if (cart.items.length === 0) {
    return <EmptyState title="Nothing to check out" description="Your cart is empty." action={<LinkButton to="/medicines">Browse products</LinkButton>} />;
  }

  const needsRx = cart.requires_prescription;
  const canPlace = selectedAddressId !== null && (!needsRx || selectedPrescriptionId !== null) && !cart.has_unavailable_items;

  return (
    <div className="space-y-5">
      <PageHeader title="Checkout" description="Confirm your delivery address and payment method." />
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                <MapPin className="h-5 w-5 text-brand-500" /> Delivery address
              </h2>
              <Button variant="outline" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setAddingAddress(true)}>
                Add new
              </Button>
            </div>
            {addresses.isLoading ? (
              <Spinner className="py-6" />
            ) : addresses.data && addresses.data.length > 0 ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {addresses.data.map((a) => (
                  <label
                    key={a.id}
                    className={cn(
                      "flex cursor-pointer gap-3 rounded-xl border p-3.5 text-sm transition-colors",
                      selectedAddressId === a.id ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-300",
                    )}
                  >
                    <input type="radio" name="address" className="mt-1 accent-brand-500" checked={selectedAddressId === a.id} onChange={() => setAddressId(a.id)} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge tone="neutral" className="capitalize">{a.address_type}</Badge>
                        {a.is_default && <Badge tone="brand">Default</Badge>}
                      </div>
                      <AddressText address={a} className="mt-1.5" />
                    </div>
                  </label>
                ))}
              </div>
            ) : (
              <div className="mt-4">
                <Alert tone="info">You have no saved addresses yet. Add one to continue.</Alert>
              </div>
            )}
          </Card>

          {needsRx && (
            <Card>
              <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                <FileUp className="h-5 w-5 text-brand-500" /> Prescription
              </h2>
              <p className="mt-1 text-sm text-muted">
                Your cart has prescription medicines, so the order is linked to a prescription you confirmed. The newest one
                that lists them is selected.
              </p>
              {prescriptions.isLoading ? (
                <Spinner className="py-6" />
              ) : usable.length === 0 ? (
                <div className="mt-4">
                  <Alert tone="warning" title="No confirmed prescription yet">
                    <Link to="/prescriptions/upload" className="font-semibold underline">Upload and confirm a prescription</Link> to continue, or remove
                    the prescription medicines from your cart.
                  </Alert>
                </div>
              ) : (
                <div className="mt-4 space-y-2">
                  {usable.map((p) => (
                    <label
                      key={p.id}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-sm",
                        selectedPrescriptionId === p.id ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-300",
                      )}
                    >
                      <input type="radio" name="prescription" className="accent-brand-500" checked={selectedPrescriptionId === p.id} onChange={() => setPrescriptionId(p.id)} />
                      <span className="flex-1">
                        <span className="font-medium text-ink">Prescription #{p.id}</span>
                        <span className="block text-xs text-muted">
                          Uploaded {formatDate(p.created_at)} · {p.item_count} medicine{p.item_count === 1 ? "" : "s"}
                        </span>
                      </span>
                      <VerificationBadge status={p.pharmacist_verification_status} />
                    </label>
                  ))}
                  <p className="text-xs text-muted">
                    If you asked a pharmacist to review the prescription, the order waits in “Awaiting pharmacist” until they do.
                  </p>
                </div>
              )}
            </Card>
          )}

          <Card>
            <h2 className="text-base font-semibold text-ink">Payment</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {(
                [
                  { value: "cod", label: "Cash on delivery", text: "Pay in cash when the order arrives.", icon: Banknote },
                  { value: "simulated_online", label: "Pay online (demo)", text: "Simulated payment. No real money is charged.", icon: CreditCard },
                ] as const
              ).map(({ value, label, text, icon: Icon }) => (
                <label
                  key={value}
                  className={cn(
                    "flex cursor-pointer gap-3 rounded-xl border p-3.5 text-sm",
                    payment === value ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-300",
                  )}
                >
                  <input type="radio" name="payment" className="mt-1 accent-brand-500" checked={payment === value} onChange={() => setPayment(value)} />
                  <Icon className="mt-0.5 h-5 w-5 text-brand-500" />
                  <span>
                    <span className="block font-semibold text-ink">{label}</span>
                    <span className="text-muted">{text}</span>
                  </span>
                </label>
              ))}
            </div>
          </Card>
        </div>

        <Card className="space-y-3 lg:sticky lg:top-24 lg:self-start">
          <h2 className="text-base font-semibold text-ink">Order summary</h2>
          <ul className="divide-y divide-line text-sm">
            {cart.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-3 py-2">
                <span className="min-w-0">
                  <span className="block truncate font-medium text-ink">{item.product.medicine_name}</span>
                  <span className="text-xs text-muted">
                    {item.product.pack_size} × {item.quantity}
                    {item.product.prescription_required && " · Rx"}
                  </span>
                </span>
                <span className="font-medium">{formatPrice(item.line_total)}</span>
              </li>
            ))}
          </ul>
          <dl className="space-y-1.5 border-t border-line pt-3 text-sm">
            <div className="flex justify-between"><dt className="text-muted">Subtotal</dt><dd>{formatPrice(cart.subtotal)}</dd></div>
            <div className="flex justify-between"><dt className="text-muted">Delivery</dt><dd>{cart.delivery_charge === 0 ? "Free" : formatPrice(cart.delivery_charge)}</dd></div>
            <div className="flex justify-between border-t border-line pt-2 text-base font-bold"><dt>Total</dt><dd>{formatPrice(cart.total)}</dd></div>
          </dl>
          <Button fullWidth size="lg" disabled={!canPlace} loading={place.isPending} onClick={() => place.mutate()}>
            Place order
          </Button>
          <p className="text-xs text-muted">By placing the order you confirm the details above are correct. Prices are re-checked when the order is placed.</p>
        </Card>
      </div>

      <Modal open={addingAddress} onClose={() => setAddingAddress(false)} title="Add delivery address" size="lg">
        <AddressForm onSubmit={(data) => createAddress.mutateAsync(data).then(() => undefined)} onCancel={() => setAddingAddress(false)} />
      </Modal>
    </div>
  );
}

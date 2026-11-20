import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, PackageCheck } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AddressText } from "@/components/AddressForm";
import { Button, LinkButton } from "@/components/ui/Button";
import { Alert, Badge, EmptyState, OrderStatusBadge, PaymentBadge, Spinner } from "@/components/ui/Feedback";
import { Input, Select } from "@/components/ui/Form";
import { Card, PageHeader } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { OrderTimeline } from "@/pages/customer/OrderDetailPage";
import { adminApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { OrderStatus } from "@/types";
import { formatDateTime, formatPrice, humanise } from "@/utils/format";
import { orderStatusLabel } from "@/utils/labels";

export default function AdminOrderDetailPage() {
  const { id } = useParams();
  const orderId = Number(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [next, setNext] = useState<OrderStatus | "">("");
  const [tracking, setTracking] = useState("");
  const [note, setNote] = useState("");

  const { data: order, isLoading, isError } = useQuery({ queryKey: ["admin", "order", orderId], queryFn: () => adminApi.order(orderId) });
  useDocumentTitle(order ? `Order ${order.order_number}` : "Order");

  const update = useMutation({
    mutationFn: (target?: OrderStatus) =>
      adminApi.updateOrderStatus(orderId, {
        order_status: target ?? (next as OrderStatus),
        tracking_reference: tracking.trim() || undefined,
        note: note.trim() || undefined,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin", "order", orderId], updated);
      queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "dashboard"] });
      setNext("");
      setTracking("");
      setNote("");
      toast.success(`Order marked as ${orderStatusLabel[updated.order_status].toLowerCase()}`);
    },
    onError: (err) => toast.error("Could not update status", toApiError(err).message),
  });

  if (isLoading) return <Spinner />;
  if (isError || !order) return <EmptyState title="Order not found" action={<LinkButton to="/admin/orders">Back to orders</LinkButton>} />;

  const allowed = order.allowed_next_statuses;

  return (
    <div className="space-y-5">
      <Link to="/admin/orders" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Back to orders</Link>
      <PageHeader eyebrow={`Placed ${formatDateTime(order.created_at)}`} title={order.order_number} actions={<><OrderStatusBadge status={order.order_status} /><PaymentBadge status={order.payment_status} /></>} />

      <Card><OrderTimeline order={order} /></Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <Card>
            <h2 className="text-base font-semibold text-ink">Items</h2>
            <ul className="mt-3 divide-y divide-line text-sm">
              {order.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <p className="font-medium text-ink">{item.product_name_snapshot}{item.prescription_required && <Badge tone="warning" className="ml-2">Rx</Badge>}</p>
                    <p className="text-xs text-muted">{item.pack_size_snapshot} · {formatPrice(item.price_snapshot)} × {item.quantity}</p>
                  </div>
                  <span className="font-medium">{formatPrice(item.subtotal)}</span>
                </li>
              ))}
            </ul>
            <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-sm">
              <div className="flex justify-between"><dt className="text-muted">Subtotal</dt><dd>{formatPrice(order.subtotal)}</dd></div>
              <div className="flex justify-between"><dt className="text-muted">Delivery</dt><dd>{order.delivery_charge === 0 ? "Free" : formatPrice(order.delivery_charge)}</dd></div>
              <div className="flex justify-between text-base font-bold"><dt>Total</dt><dd>{formatPrice(order.order_total)}</dd></div>
            </dl>
          </Card>
          <div className="grid gap-5 md:grid-cols-2">
            <Card>
              <h2 className="text-sm font-semibold text-ink">Delivery address</h2>
              <AddressText address={order.address_snapshot} className="mt-2 text-sm" />
            </Card>
            <Card>
              <h2 className="text-sm font-semibold text-ink">Payment & shipment</h2>
              <p className="mt-2 text-sm">{order.payment_method === "cod" ? "Cash on delivery" : "Online (simulated)"}</p>
              <ul className="mt-1 space-y-0.5 text-xs text-muted">
                {order.payments.map((p) => <li key={p.id}>{humanise(p.payment_status)} · {formatPrice(p.amount)}{p.transaction_reference && ` · ${p.transaction_reference}`}</li>)}
              </ul>
              {order.shipment && (
                <p className="mt-3 text-xs text-muted">Shipment: {humanise(order.shipment.shipment_status)}{order.shipment.tracking_reference && ` · ${order.shipment.tracking_reference}`}</p>
              )}
              {order.prescription_id && (
                <p className="mt-2 text-xs">
                  Prescription: <Link to={`/admin/prescriptions/${order.prescription_id}`} className="font-semibold text-brand-600 hover:underline">#{order.prescription_id}</Link>
                </p>
              )}
            </Card>
          </div>
        </div>

        <Card className="space-y-3 lg:self-start">
          <h2 className="text-base font-semibold text-ink">Update status</h2>
          {allowed.length === 0 ? (
            <p className="text-sm text-muted">This order is {orderStatusLabel[order.order_status].toLowerCase()} and cannot change further.</p>
          ) : (
            <>
              {order.order_status === "verification_pending" && (
                <Alert tone="warning">The customer asked for a pharmacist review. Approving it moves the order to “verified”; you can also move it on yourself.</Alert>
              )}
              {allowed.includes("delivered") && (
                <Button fullWidth size="lg" leftIcon={<PackageCheck className="h-5 w-5" />} loading={update.isPending && update.variables === "delivered"} onClick={() => update.mutate("delivered")}>
                  Mark as delivered
                </Button>
              )}
              <div className="border-t border-line pt-3">
                <Select label="Or move to another stage" value={next} placeholder="Choose…" options={allowed.map((s) => ({ value: s, label: orderStatusLabel[s] }))} onChange={(e) => setNext(e.target.value as OrderStatus)} />
              </div>
              {next === "shipped" && <Input label="Tracking reference" hint="Leave empty to generate one." value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={40} />}
              {next === "cancelled" && <Input label="Reason" value={note} onChange={(e) => setNote(e.target.value)} maxLength={255} />}
              <Button fullWidth variant={next === "cancelled" ? "danger" : "outline"} disabled={!next} loading={update.isPending && update.variables === undefined} onClick={() => update.mutate(undefined)}>
                {next ? `Mark as ${orderStatusLabel[next as OrderStatus].toLowerCase()}` : "Update"}
              </Button>
              <p className="text-xs text-muted">Stages can be skipped: this demo has no courier, so you decide when an order is delivered. Delivering a COD order marks it as paid. Cancelling restocks the items and records a simulated refund for online payments.</p>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

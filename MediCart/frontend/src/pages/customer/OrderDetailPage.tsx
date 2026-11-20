import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AddressText } from "@/components/AddressForm";
import { Button, LinkButton } from "@/components/ui/Button";
import { Alert, Badge, EmptyState, OrderStatusBadge, PaymentBadge, Spinner } from "@/components/ui/Feedback";
import { Textarea } from "@/components/ui/Form";
import { Card, ConfirmDialog, PageHeader } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { orderApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { OrderDetail, OrderStatus } from "@/types";
import { cn } from "@/utils/cn";
import { formatDateTime, formatPrice, humanise } from "@/utils/format";
import { orderStatusLabel } from "@/utils/labels";

export function OrderTimeline({ order }: { order: OrderDetail }) {
  // Show the pharmacist step only for orders that actually went through a review.
  const reviewed = order.order_status === "verification_pending" || order.order_status === "verified";
  const steps: OrderStatus[] = reviewed
    ? ["verification_pending", "verified", "processing", "packed", "shipped", "delivered"]
    : ["placed", "processing", "packed", "shipped", "delivered"];
  if (order.order_status === "cancelled") {
    return <Alert tone="error" title="Order cancelled">{order.cancellation_reason ?? "This order was cancelled."}</Alert>;
  }
  const currentIndex = Math.max(steps.indexOf(order.order_status), 0);
  return (
    <ol className="grid gap-2 sm:grid-cols-5 lg:grid-cols-6">
      {steps.map((step, i) => {
        const done = i <= currentIndex;
        return (
          <li key={step} className="flex items-center gap-2 sm:flex-col sm:items-start">
            <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold", done ? "bg-brand-500 text-white" : "bg-brand-100 text-muted")}>
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </span>
            <span className={cn("text-xs font-medium", done ? "text-ink" : "text-muted")}>{orderStatusLabel[step]}</span>
          </li>
        );
      })}
    </ol>
  );
}

export default function OrderDetailPage() {
  const { id } = useParams();
  const orderId = Number(id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");

  const { data: order, isLoading, isError } = useQuery({ queryKey: ["order", orderId], queryFn: () => orderApi.get(orderId) });
  useDocumentTitle(order ? `Order ${order.order_number}` : "Order");

  const cancel = useMutation({
    mutationFn: () => orderApi.cancel(orderId, reason.trim() || undefined),
    onSuccess: (updated) => {
      queryClient.setQueryData(["order", orderId], updated);
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      setCancelOpen(false);
      toast.success("Order cancelled", updated.payment_status === "refunded" ? "A simulated refund has been recorded." : undefined);
    },
    onError: (err) => toast.error("Could not cancel", toApiError(err).message),
  });

  if (isLoading) return <Spinner label="Loading order" />;
  if (isError || !order) return <EmptyState title="Order not found" action={<LinkButton to="/orders">Back to orders</LinkButton>} />;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Order"
        title={order.order_number}
        description={
          order.delivered_at
            ? `Placed ${formatDateTime(order.created_at)} · Delivered ${formatDateTime(order.delivered_at)}`
            : `Placed ${formatDateTime(order.created_at)}`
        }
        actions={
          <>
            <OrderStatusBadge status={order.order_status} />
            <PaymentBadge status={order.payment_status} />
            {order.can_cancel && (
              <Button variant="outline" size="sm" onClick={() => setCancelOpen(true)}>
                Cancel order
              </Button>
            )}
          </>
        }
      />

      <Card>
        <OrderTimeline order={order} />
        {order.order_status === "verification_pending" && order.prescription_id && (
          <p className="mt-4 text-sm text-muted">
            Waiting for a pharmacist to verify{" "}
            <Link to={`/prescriptions/${order.prescription_id}`} className="font-semibold text-brand-600 hover:underline">
              prescription #{order.prescription_id}
            </Link>
            .
          </p>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card>
          <h2 className="text-base font-semibold text-ink">Items</h2>
          <ul className="mt-3 divide-y divide-line text-sm">
            {order.items.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 py-2.5">
                <div>
                  <p className="font-medium text-ink">
                    {item.product_id ? <Link to={`/medicines`} className="hover:text-brand-600">{item.product_name_snapshot}</Link> : item.product_name_snapshot}
                    {item.prescription_required && <Badge tone="warning" className="ml-2">Rx</Badge>}
                  </p>
                  <p className="text-xs text-muted">
                    {item.pack_size_snapshot} · {formatPrice(item.price_snapshot)} × {item.quantity}
                  </p>
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

        <div className="space-y-5">
          <Card>
            <h2 className="text-base font-semibold text-ink">Delivery address</h2>
            <AddressText address={order.address_snapshot} className="mt-2 text-sm" />
          </Card>
          <Card>
            <h2 className="text-base font-semibold text-ink">Payment</h2>
            <p className="mt-2 text-sm text-ink">{order.payment_method === "cod" ? "Cash on delivery" : "Online payment (simulated)"}</p>
            <ul className="mt-2 space-y-1 text-xs text-muted">
              {order.payments.map((p) => (
                <li key={p.id}>
                  {humanise(p.payment_status)} · {formatPrice(p.amount)}
                  {p.transaction_reference && ` · Ref ${p.transaction_reference}`}
                </li>
              ))}
            </ul>
          </Card>
          {order.shipment && (
            <Card>
              <h2 className="text-base font-semibold text-ink">Shipment</h2>
              <p className="mt-2 text-sm text-ink">{humanise(order.shipment.shipment_status)}</p>
              {order.shipment.tracking_reference && <p className="text-xs text-muted">Tracking ID {order.shipment.tracking_reference}</p>}
              <p className="text-xs text-muted">Updated {formatDateTime(order.shipment.updated_at)}</p>
            </Card>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onConfirm={() => cancel.mutate()}
        loading={cancel.isPending}
        title="Cancel this order?"
        description="Stock is released immediately. Online payments are refunded (simulated)."
        confirmLabel="Cancel order"
        tone="danger"
      >
        <Textarea label="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} />
      </ConfirmDialog>
    </div>
  );
}

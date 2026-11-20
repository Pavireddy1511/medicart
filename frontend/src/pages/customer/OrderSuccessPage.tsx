import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock } from "lucide-react";
import { useParams } from "react-router-dom";

import { LinkButton } from "@/components/ui/Button";
import { OrderStatusBadge, PaymentBadge, Spinner } from "@/components/ui/Feedback";
import { Card } from "@/components/ui/Layout";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { orderApi } from "@/services/api";
import { formatPrice } from "@/utils/format";

export default function OrderSuccessPage() {
  useDocumentTitle("Order placed");
  const { id } = useParams();
  const { data: order, isLoading } = useQuery({ queryKey: ["order", Number(id)], queryFn: () => orderApi.get(Number(id)) });

  if (isLoading || !order) return <Spinner />;
  const waiting = order.order_status === "verification_pending";

  return (
    <div className="mx-auto max-w-xl space-y-5 py-6 text-center">
      <span className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full ${waiting ? "bg-amber-100 text-amber-600" : "bg-emerald-100 text-emerald-600"}`}>
        {waiting ? <Clock className="h-8 w-8" /> : <CheckCircle2 className="h-8 w-8" />}
      </span>
      <div>
        <h1 className="text-2xl font-bold text-ink">{waiting ? "Order received, pending verification" : "Order placed"}</h1>
        <p className="mt-2 text-sm text-muted">
          Order <span className="font-semibold text-ink">{order.order_number}</span>
          {waiting
            ? ". A pharmacist will verify your prescription before we start processing it."
            : ". We'll start preparing your order shortly."}
        </p>
      </div>
      <Card className="text-left">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <OrderStatusBadge status={order.order_status} />
          <PaymentBadge status={order.payment_status} />
        </div>
        <ul className="mt-3 divide-y divide-line text-sm">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between py-2">
              <span>
                {item.product_name_snapshot} <span className="text-muted">× {item.quantity}</span>
              </span>
              <span className="font-medium">{formatPrice(item.subtotal)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex justify-between border-t border-line pt-3 font-bold">
          <span>Total paid{order.payment_method === "cod" ? " on delivery" : ""}</span>
          <span>{formatPrice(order.order_total)}</span>
        </div>
      </Card>
      <div className="flex flex-wrap justify-center gap-2">
        <LinkButton to={`/orders/${order.id}`}>Track order</LinkButton>
        <LinkButton to="/medicines" variant="outline">Continue shopping</LinkButton>
      </div>
    </div>
  );
}

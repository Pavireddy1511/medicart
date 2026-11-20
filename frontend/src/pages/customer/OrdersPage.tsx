import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronRight, Package } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { LinkButton } from "@/components/ui/Button";
import { EmptyState, OrderStatusBadge, PaymentBadge, Spinner } from "@/components/ui/Feedback";
import { PageHeader } from "@/components/ui/Layout";
import { Tabs } from "@/components/ui/Tabs";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { orderApi } from "@/services/api";
import type { OrderSummary } from "@/types";
import { formatDate, formatDateTime, formatPrice } from "@/utils/format";

type Filter = "all" | "active" | "delivered" | "cancelled";

const matches: Record<Filter, (o: OrderSummary) => boolean> = {
  all: () => true,
  active: (o) => o.order_status !== "delivered" && o.order_status !== "cancelled",
  delivered: (o) => o.order_status === "delivered",
  cancelled: (o) => o.order_status === "cancelled",
};

export default function OrdersPage() {
  useDocumentTitle("My orders");
  const [filter, setFilter] = useState<Filter>("all");
  const { data, isLoading } = useQuery({ queryKey: ["orders"], queryFn: orderApi.list });

  if (isLoading) return <Spinner label="Loading orders" />;
  if (!data || data.length === 0) {
    return <EmptyState icon={Package} title="No orders yet" description="Your orders will appear here once you place one." action={<LinkButton to="/medicines">Start shopping</LinkButton>} />;
  }

  const count = (f: Filter) => data.filter(matches[f]).length;
  const visible = data.filter(matches[filter]);

  return (
    <div className="space-y-5">
      <PageHeader title="My orders" description={`${data.length} order${data.length === 1 ? "" : "s"}`} />
      <Tabs
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: "All", count: data.length },
          { value: "active", label: "In progress", count: count("active") },
          { value: "delivered", label: "Delivered", count: count("delivered") },
          { value: "cancelled", label: "Cancelled", count: count("cancelled") },
        ]}
      />
      {visible.length === 0 ? (
        <EmptyState title="Nothing here" description="No orders match this filter." />
      ) : (
        <ul className="space-y-3">
          {visible.map((order) => (
            <li key={order.id}>
              <Link to={`/orders/${order.id}`} className="block rounded-2xl border border-line bg-white p-4 shadow-card transition-colors hover:border-brand-300">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-ink">{order.order_number}</p>
                    <p className="text-xs text-muted">Ordered {formatDateTime(order.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <OrderStatusBadge status={order.order_status} />
                    <PaymentBadge status={order.payment_status} />
                  </div>
                </div>
                {order.delivered_at && (
                  <p className="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" /> Delivered on {formatDate(order.delivered_at)}
                  </p>
                )}
                <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                  <p className="truncate text-muted">
                    {order.items.slice(0, 3).map((i) => i.product_name_snapshot).join(", ")}
                    {order.items.length > 3 && ` +${order.items.length - 3} more`}
                  </p>
                  <p className="flex items-center gap-1 font-semibold text-ink">
                    {formatPrice(order.order_total)} <ChevronRight className="h-4 w-4 text-muted" />
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

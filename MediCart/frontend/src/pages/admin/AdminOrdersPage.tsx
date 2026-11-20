import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageCheck, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { EmptyState, OrderStatusBadge, PaymentBadge, Spinner } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Form";
import { PageHeader, Pagination, Table, td, th } from "@/components/ui/Layout";
import { Tabs } from "@/components/ui/Tabs";
import { useDebounce, useDocumentTitle } from "@/hooks/useUtilities";
import { useToast } from "@/context/ToastContext";
import { adminApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { OrderStatus } from "@/types";
import { formatDate, formatDateTime, formatPrice } from "@/utils/format";
import { orderStatusLabel } from "@/utils/labels";

type Filter = "" | OrderStatus;
const filters: { value: Filter; label: string }[] = [
  { value: "", label: "All" },
  { value: "placed", label: "Placed" },
  { value: "verification_pending", label: "Awaiting pharmacist" },
  { value: "verified", label: "Verified" },
  { value: "processing", label: "Processing" },
  { value: "packed", label: "Packed" },
  { value: "shipped", label: "Shipped" },
  { value: "delivered", label: "Delivered" },
  { value: "cancelled", label: "Cancelled" },
];

export default function AdminOrdersPage() {
  useDocumentTitle("Orders");
  const [status, setStatus] = useState<Filter>("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounce(q.trim(), 300);

  const queryClient = useQueryClient();
  const toast = useToast();
  const deliver = useMutation({
    mutationFn: (orderId: number) => adminApi.updateOrderStatus(orderId, { order_status: "delivered" }),
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      toast.success(`${order.order_number} marked as delivered`);
    },
    onError: (err) => toast.error("Could not update the order", toApiError(err).message),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "orders", status, search, page],
    queryFn: () => adminApi.orders({ status: status || undefined, q: search || undefined, page, page_size: 20 }),
    placeholderData: (prev) => prev,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-5">
      <PageHeader title="Orders" description="Update fulfilment status and review payments." />
      <Tabs value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={filters} />
      <Input placeholder="Search order number, customer name or mobile" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} leftIcon={<Search className="h-4 w-4" />} />
      {isLoading && !data ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No orders" description={status ? `No orders are ${orderStatusLabel[status].toLowerCase()}.` : "Orders will appear here once customers check out."} />
      ) : (
        <>
          <Table>
            <thead className="bg-surface">
              <tr>
                <th className={th}>Order</th>
                <th className={th}>Customer</th>
                <th className={th}>Items</th>
                <th className={th}>Status</th>
                <th className={th}>Payment</th>
                <th className={`${th} text-right`}>Total</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.items.map((o) => (
                <tr key={o.id} className="hover:bg-brand-50/40">
                  <td className={td}>
                    <Link to={`/admin/orders/${o.id}`} className="font-semibold text-brand-600 hover:underline">{o.order_number}</Link>
                    <p className="text-xs text-muted">{formatDateTime(o.created_at)}</p>
                  </td>
                  <td className={td}>
                    <p>{o.customer_name}</p>
                    <p className="text-xs text-muted">{o.customer_mobile}</p>
                  </td>
                  <td className={`${td} text-xs`}>
                    {o.item_count} item{o.item_count === 1 ? "" : "s"}
                    {o.items.some((i) => i.prescription_required) && <span className="ml-1 text-amber-700">· Rx</span>}
                  </td>
                  <td className={td}><OrderStatusBadge status={o.order_status} /></td>
                  <td className={td}><PaymentBadge status={o.payment_status} /></td>
                  <td className={`${td} text-right font-semibold`}>{formatPrice(o.order_total)}</td>
                  <td className={`${td} text-right`}>
                    {o.allowed_next_statuses.includes("delivered") ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        leftIcon={<PackageCheck className="h-4 w-4" />}
                        loading={deliver.isPending && deliver.variables === o.id}
                        disabled={deliver.isPending}
                        onClick={() => deliver.mutate(o.id)}
                      >
                        Mark delivered
                      </Button>
                    ) : o.delivered_at ? (
                      <span className="whitespace-nowrap text-xs text-emerald-700">Delivered {formatDate(o.delivered_at)}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}

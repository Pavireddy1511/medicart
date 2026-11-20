import { useQuery } from "@tanstack/react-query";
import { FileText, IndianRupee, Package, Pill, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { OrderStatusBadge, Spinner } from "@/components/ui/Feedback";
import { Card, PageHeader, Stat, Table, td, th } from "@/components/ui/Layout";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi } from "@/services/api";
import type { OrderStatus } from "@/types";
import { formatDateTime, formatPrice } from "@/utils/format";
import { orderStatusLabel } from "@/utils/labels";

export default function AdminDashboardPage() {
  useDocumentTitle("Admin overview");
  const { data, isLoading } = useQuery({ queryKey: ["admin", "dashboard"], queryFn: adminApi.dashboard, refetchInterval: 60_000 });

  if (isLoading || !data) return <Spinner label="Loading dashboard" />;

  const statusEntries = Object.entries(data.orders_by_status) as [OrderStatus, number][];
  const maxStatus = Math.max(1, ...statusEntries.map(([, n]) => n));
  const rx = data.prescriptions;

  return (
    <div className="space-y-6">
      <PageHeader title="Overview" description="Live figures from the database. Revenue is simulated - no real payments are processed." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Customers" value={data.total_customers} icon={<Users className="h-5 w-5" />} />
        <Stat label="Active medicines" value={data.total_medicines} hint={`${data.total_products} pack variants`} icon={<Pill className="h-5 w-5" />} />
        <Stat label="Orders" value={data.total_orders} hint={`${data.pending_orders} open · ${data.completed_orders} delivered · ${data.cancelled_orders} cancelled`} icon={<Package className="h-5 w-5" />} />
        <Stat label="Simulated revenue" value={formatPrice(data.simulated_revenue)} hint="Excludes cancelled orders" icon={<IndianRupee className="h-5 w-5" />} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="text-base font-semibold text-ink">Orders by status</h2>
          {statusEntries.length === 0 ? (
            <p className="mt-3 text-sm text-muted">No orders yet.</p>
          ) : (
            <ul className="mt-4 space-y-2.5">
              {statusEntries.map(([status, count]) => (
                <li key={status} className="grid grid-cols-[140px_1fr_40px] items-center gap-3 text-sm">
                  <span className="truncate text-muted">{orderStatusLabel[status] ?? status}</span>
                  <div className="h-2.5 rounded-full bg-brand-100">
                    <div className="h-full rounded-full bg-brand-500" style={{ width: `${(count / maxStatus) * 100}%` }} />
                  </div>
                  <span className="text-right font-semibold tabular-nums">{count}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold text-ink"><FileText className="h-4 w-4 text-brand-500" /> Prescription processing</h2>
            <Link to="/admin/prescriptions" className="text-sm font-semibold text-brand-600 hover:underline">View all</Link>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {[
              ["Uploaded", rx.total],
              ["Awaiting customer", rx.awaiting_confirmation],
              ["Pending verification", rx.pending_verification],
              ["Clarification", rx.clarification_requested],
              ["Approved", rx.approved],
              ["Rejected", rx.rejected],
              ["Uncertain items", rx.uncertain_items],
              ["AI fallback used", rx.ai_fallback],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-xl bg-surface p-3">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="text-lg font-bold text-ink">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted">AI output is never treated as a verified prescription; every record above is reviewed by the customer and, where needed, a pharmacist.</p>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card padded={false}>
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="text-base font-semibold text-ink">Recent orders</h2>
            <Link to="/admin/orders" className="text-sm font-semibold text-brand-600 hover:underline">All orders</Link>
          </div>
          <Table className="rounded-none border-0 shadow-none">
            <thead className="bg-surface">
              <tr>
                <th className={th}>Order</th>
                <th className={th}>Customer</th>
                <th className={th}>Status</th>
                <th className={`${th} text-right`}>Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.recent_orders.map((o) => (
                <tr key={o.id} className="hover:bg-brand-50/40">
                  <td className={td}>
                    <Link to={`/admin/orders/${o.id}`} className="font-semibold text-brand-600 hover:underline">{o.order_number}</Link>
                    <p className="text-xs text-muted">{formatDateTime(o.created_at)}</p>
                  </td>
                  <td className={td}>
                    <p>{o.customer_name}</p>
                    <p className="text-xs text-muted">{o.customer_mobile}</p>
                  </td>
                  <td className={td}><OrderStatusBadge status={o.order_status} /></td>
                  <td className={`${td} text-right font-semibold`}>{formatPrice(o.order_total)}</td>
                </tr>
              ))}
              {data.recent_orders.length === 0 && (
                <tr><td className={`${td} text-muted`} colSpan={4}>No orders yet.</td></tr>
              )}
            </tbody>
          </Table>
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-ink">Low stock</h2>
            <Link to="/admin/medicines" className="text-sm font-semibold text-brand-600 hover:underline">Manage</Link>
          </div>
          {data.low_stock.length === 0 ? (
            <p className="mt-3 text-sm text-muted">All products have more than 10 units.</p>
          ) : (
            <ul className="mt-3 divide-y divide-line text-sm">
              {data.low_stock.map((p) => (
                <li key={p.product_id} className="flex items-center justify-between py-2">
                  <span>
                    <span className="block font-medium text-ink">{p.medicine_name}</span>
                    <span className="text-xs text-muted">{p.pack_size}</span>
                  </span>
                  <span className={`font-bold ${p.available_quantity === 0 ? "text-rose-600" : "text-amber-600"}`}>{p.available_quantity}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

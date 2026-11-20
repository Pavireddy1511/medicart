import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import { Badge, EmptyState, Spinner } from "@/components/ui/Feedback";
import { Input, Select, Toggle } from "@/components/ui/Form";
import { PageHeader, Pagination, Table, td, th } from "@/components/ui/Layout";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { useDebounce, useDocumentTitle } from "@/hooks/useUtilities";
import { adminApi } from "@/services/api";
import { toApiError } from "@/services/http";
import { formatDate } from "@/utils/format";

export default function AdminUsersPage() {
  useDocumentTitle("Customers & staff");
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounce(q.trim(), 300);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "users", search, role, page],
    queryFn: () => adminApi.users({ q: search || undefined, role: role || undefined, page, page_size: 20 }),
    placeholderData: (prev) => prev,
  });

  const update = useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: { role?: string; is_active?: boolean } }) => adminApi.updateUser(id, changes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      toast.success("User updated");
    },
    onError: (err) => toast.error("Could not update user", toApiError(err).message),
  });

  return (
    <div className="space-y-5">
      <PageHeader title="Customers & staff" description="Only administrators can grant pharmacist or admin access." />
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input placeholder="Search by name, mobile or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} leftIcon={<Search className="h-4 w-4" />} className="flex-1" />
        <Select
          value={role}
          placeholder="All roles"
          options={[{ value: "customer", label: "Customers" }, { value: "pharmacist", label: "Pharmacists" }, { value: "admin", label: "Administrators" }]}
          onChange={(e) => { setRole(e.target.value); setPage(1); }}
          className="sm:w-48"
        />
      </div>
      {isLoading && !data ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No users found" />
      ) : (
        <>
          <Table>
            <thead className="bg-surface">
              <tr>
                <th className={th}>User</th>
                <th className={th}>Contact</th>
                <th className={th}>Role</th>
                <th className={th}>Orders</th>
                <th className={th}>Joined</th>
                <th className={th}>Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.items.map((u) => {
                const self = u.id === me?.id;
                return (
                  <tr key={u.id}>
                    <td className={td}>
                      <p className="font-semibold">{u.full_name}{self && <Badge tone="brand" className="ml-2">You</Badge>}</p>
                      <p className="text-xs text-muted">ID {u.id}</p>
                    </td>
                    <td className={`${td} text-xs`}>
                      <p>+91 {u.mobile_number}</p>
                      <p className="text-muted">{u.email ?? "-"}</p>
                    </td>
                    <td className={td}>
                      <Select
                        aria-label={`Role for ${u.full_name}`}
                        value={u.role}
                        disabled={self || update.isPending}
                        options={[{ value: "customer", label: "Customer" }, { value: "pharmacist", label: "Pharmacist" }, { value: "admin", label: "Admin" }]}
                        onChange={(e) => update.mutate({ id: u.id, changes: { role: e.target.value } })}
                        className="w-36"
                      />
                    </td>
                    <td className={td}>{u.order_count}</td>
                    <td className={`${td} text-xs text-muted`}>{formatDate(u.created_at)}</td>
                    <td className={td}>
                      <Toggle checked={u.is_active} disabled={self || update.isPending} label={`Active status for ${u.full_name}`} onChange={(next) => update.mutate({ id: u.id, changes: { is_active: next } })} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}

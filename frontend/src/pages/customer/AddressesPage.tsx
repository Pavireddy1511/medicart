import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, Pencil, Plus, Star, Trash2 } from "lucide-react";
import { useState } from "react";

import { AddressForm, AddressText } from "@/components/AddressForm";
import { Button } from "@/components/ui/Button";
import { Badge, EmptyState, Spinner } from "@/components/ui/Feedback";
import { Card, ConfirmDialog, Modal, PageHeader } from "@/components/ui/Layout";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { addressApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { Address, AddressInput } from "@/types";

export default function AddressesPage() {
  useDocumentTitle("Saved addresses");
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<Address | null | "new">(null);
  const [deleting, setDeleting] = useState<Address | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["addresses"], queryFn: addressApi.list });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["addresses"] });

  const save = useMutation({
    mutationFn: (payload: { id?: number; data: AddressInput }) =>
      payload.id ? addressApi.update(payload.id, payload.data) : addressApi.create(payload.data),
    onSuccess: () => {
      refresh();
      setEditing(null);
      toast.success("Address saved");
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => addressApi.remove(id),
    onSuccess: () => {
      refresh();
      setDeleting(null);
      toast.info("Address removed");
    },
    onError: (err) => toast.error("Could not delete", toApiError(err).message),
  });
  const setDefault = useMutation({
    mutationFn: (id: number) => addressApi.setDefault(id),
    onSuccess: refresh,
    onError: (err) => toast.error("Could not update", toApiError(err).message),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="Saved addresses"
        description="Up to 10 delivery addresses."
        actions={
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setEditing("new")}>
            Add address
          </Button>
        }
      />
      {isLoading ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <EmptyState icon={MapPin} title="No addresses saved" description="Add an address to speed up checkout." action={<Button onClick={() => setEditing("new")}>Add address</Button>} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((a) => (
            <Card key={a.id} className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Badge tone="neutral" className="capitalize">{a.address_type}</Badge>
                {a.is_default && <Badge tone="brand">Default</Badge>}
              </div>
              <AddressText address={a} className="text-sm" />
              <div className="mt-auto flex flex-wrap gap-2 border-t border-line pt-3">
                <Button variant="outline" size="sm" leftIcon={<Pencil className="h-3.5 w-3.5" />} onClick={() => setEditing(a)}>Edit</Button>
                {!a.is_default && (
                  <Button variant="ghost" size="sm" leftIcon={<Star className="h-3.5 w-3.5" />} onClick={() => setDefault.mutate(a.id)}>Make default</Button>
                )}
                <Button variant="ghost" size="sm" className="ml-auto text-rose-600 hover:bg-rose-50" leftIcon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setDeleting(a)}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === "new" ? "Add address" : "Edit address"} size="lg">
        {editing !== null && (
          <AddressForm
            initial={editing === "new" ? null : editing}
            onSubmit={(formData) => save.mutateAsync({ id: editing === "new" ? undefined : editing.id, data: formData }).then(() => undefined)}
            onCancel={() => setEditing(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
        loading={remove.isPending}
        title="Delete this address?"
        description="Past orders keep a copy of the address they were delivered to."
        confirmLabel="Delete"
        tone="danger"
      />
    </div>
  );
}

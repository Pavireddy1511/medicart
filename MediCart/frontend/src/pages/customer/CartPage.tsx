import { FileUp, ShoppingCart, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { Button, LinkButton } from "@/components/ui/Button";
import { Price, ProductImage, QuantityStepper } from "@/components/ui/Commerce";
import { Alert, Badge, EmptyState, Spinner } from "@/components/ui/Feedback";
import { Card, PageHeader } from "@/components/ui/Layout";
import { useCart } from "@/hooks/useCart";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { formatPrice } from "@/utils/format";

export default function CartPage() {
  useDocumentTitle("Cart");
  const navigate = useNavigate();
  const { cart, isLoading, update, remove, clear } = useCart();

  if (isLoading || !cart) return <Spinner label="Loading your cart" />;

  if (cart.items.length === 0) {
    return (
      <EmptyState
        icon={ShoppingCart}
        title="Your cart is empty"
        description="Browse the catalogue or upload a prescription to get started."
        action={
          <div className="flex gap-2">
            <LinkButton to="/medicines">Browse products</LinkButton>
            <LinkButton to="/prescriptions/upload" variant="secondary" leftIcon={<FileUp className="h-4 w-4" />}>
              Upload prescription
            </LinkButton>
          </div>
        }
      />
    );
  }

  const remaining = cart.free_delivery_above - cart.subtotal;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Shopping cart"
        description={`${cart.item_count} item${cart.item_count === 1 ? "" : "s"}`}
        actions={
          <Button variant="ghost" size="sm" onClick={() => clear.mutate()} loading={clear.isPending}>
            Clear cart
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-3">
          {cart.has_unavailable_items && (
            <Alert tone="warning" title="Some items are no longer available in the quantity requested">
              Reduce the quantity or remove them to continue to checkout.
            </Alert>
          )}
          {cart.items.map((item) => (
            <Card key={item.id} className="flex gap-4">
              <Link to={`/medicines/${item.product.medicine_id}`} className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-surface">
                <ProductImage
                  medicine={{ medicine_name: item.product.medicine_name, image_url: item.product.image_url, category: null }}
                  iconClassName="h-8 w-8"
                />
              </Link>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <Link to={`/medicines/${item.product.medicine_id}`} className="block truncate font-semibold text-ink hover:text-brand-600">
                      {item.product.medicine_name}
                    </Link>
                    <p className="text-xs text-muted">
                      {[item.product.brand_name, item.product.strength, item.product.pack_size].filter(Boolean).join(" · ")}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {item.product.prescription_required && <Badge tone="warning">Rx</Badge>}
                      {!item.in_stock && <Badge tone="danger">Only {item.product.available_quantity} available</Badge>}
                      {item.price_changed && <Badge tone="info">Price updated</Badge>}
                    </div>
                  </div>
                  <Price price={item.line_total} />
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                  <QuantityStepper
                    size="sm"
                    value={item.quantity}
                    max={Math.min(20, Math.max(item.quantity, item.product.available_quantity))}
                    onChange={(quantity) => update.mutate({ itemId: item.id, quantity })}
                    disabled={update.isPending}
                  />
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-muted">{formatPrice(item.unit_price)} each</span>
                    <button
                      type="button"
                      onClick={() => remove.mutate(item.id)}
                      className="inline-flex items-center gap-1 text-muted hover:text-rose-600"
                    >
                      <Trash2 className="h-4 w-4" /> Remove
                    </button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>

        <div className="space-y-3 lg:sticky lg:top-24 lg:self-start">
          <Card>
            <h2 className="text-base font-semibold text-ink">Order summary</h2>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted">Subtotal</dt>
                <dd className="font-medium">{formatPrice(cart.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted">Delivery</dt>
                <dd className="font-medium">{cart.delivery_charge === 0 ? <span className="text-emerald-600">Free</span> : formatPrice(cart.delivery_charge)}</dd>
              </div>
              <div className="flex justify-between border-t border-line pt-2 text-base">
                <dt className="font-semibold">Total</dt>
                <dd className="font-bold">{formatPrice(cart.total)}</dd>
              </div>
            </dl>
            {remaining > 0 && (
              <p className="mt-3 rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700">
                Add {formatPrice(remaining)} more for free delivery.
              </p>
            )}
            <Button fullWidth size="lg" className="mt-4" disabled={cart.has_unavailable_items} onClick={() => navigate("/checkout")}>
              Proceed to checkout
            </Button>
          </Card>
          {cart.requires_prescription && (
            <Alert tone="warning" title="Prescription medicines in cart">
              The order is linked to the prescription you confirmed for them.{" "}
              <Link to="/prescriptions/upload" className="font-semibold underline">Upload one now</Link>
            </Alert>
          )}
        </div>
      </div>
    </div>
  );
}

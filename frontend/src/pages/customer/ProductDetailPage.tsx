import { useQuery } from "@tanstack/react-query";
import { ChevronRight, FileUp, ShieldAlert, ShoppingCart } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button, LinkButton } from "@/components/ui/Button";
import { Price, ProductImage, QuantityStepper } from "@/components/ui/Commerce";
import { Alert, Badge, EmptyState, Skeleton } from "@/components/ui/Feedback";
import { Card } from "@/components/ui/Layout";
import { useCart } from "@/hooks/useCart";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { catalogueApi } from "@/services/api";
import { cn } from "@/utils/cn";
import { recentlyViewed } from "@/utils/storage";

export default function ProductDetailPage() {
  const { id } = useParams();
  const medicineId = Number(id);
  const { add } = useCart();
  const [productId, setProductId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);

  const { data: medicine, isLoading, isError } = useQuery({
    queryKey: ["medicine", medicineId],
    queryFn: () => catalogueApi.medicine(medicineId),
    enabled: Number.isFinite(medicineId),
  });

  useDocumentTitle(medicine?.medicine_name ?? "Product");

  useEffect(() => {
    if (medicine) recentlyViewed.push(medicine.id);
  }, [medicine]);

  if (isLoading) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="aspect-square" />
        <div className="space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-24" />
        </div>
      </div>
    );
  }
  if (isError || !medicine) {
    return <EmptyState title="Product not found" description="It may have been removed from the catalogue." action={<LinkButton to="/medicines">Back to catalogue</LinkButton>} />;
  }

  // Until the customer picks a pack, default to the first one in stock.
  const product =
    medicine.products.find((p) => p.id === productId) ??
    medicine.products.find((p) => p.in_stock) ??
    medicine.products[0];
  const maxQty = Math.min(20, product?.available_quantity ?? 0);

  const details: [string, string | null][] = [
    ["Brand", medicine.brand_name],
    ["Composition", medicine.composition ?? medicine.generic_name],
    ["Strength", medicine.strength],
    ["Formulation", medicine.formulation],
    ["Manufacturer", medicine.manufacturer],
    ["Category", medicine.category?.name ?? null],
  ];

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1 text-sm text-muted" aria-label="Breadcrumb">
        <Link to="/medicines" className="hover:text-ink">Products</Link>
        {medicine.category && (
          <>
            <ChevronRight className="h-4 w-4" />
            <Link to={`/medicines?category=${medicine.category.slug}`} className="hover:text-ink">{medicine.category.name}</Link>
          </>
        )}
        <ChevronRight className="h-4 w-4" />
        <span className="truncate text-ink">{medicine.medicine_name}</span>
      </nav>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <Card padded={false} className="aspect-square overflow-hidden">
          <ProductImage medicine={medicine} iconClassName="h-24 w-24" />
        </Card>

        <div className="space-y-5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {medicine.prescription_required ? <Badge tone="warning">Prescription required</Badge> : <Badge tone="success">No prescription needed</Badge>}
              {product && product.discount_percent > 0 && <Badge tone="brand">{product.discount_percent}% off</Badge>}
            </div>
            <h1 className="mt-2 text-2xl font-bold text-ink sm:text-3xl">{medicine.medicine_name}</h1>
            <p className="mt-1 text-sm text-muted">
              {[medicine.brand_name, medicine.strength, medicine.formulation].filter(Boolean).join(" · ")}
              {medicine.manufacturer && <> · by {medicine.manufacturer}</>}
            </p>
          </div>

          {medicine.products.length > 1 && (
            <div>
              <p className="mb-2 text-sm font-medium text-ink">Pack size</p>
              <div className="flex flex-wrap gap-2">
                {medicine.products.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setProductId(p.id);
                      setQuantity(1);
                    }}
                    className={cn(
                      "rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                      p.id === product?.id ? "border-brand-500 bg-brand-50 text-brand-700" : "border-line bg-white hover:border-brand-300",
                      !p.in_stock && "opacity-60",
                    )}
                  >
                    <span className="block font-semibold">{p.pack_size}</span>
                    <span className="block text-xs text-muted">{p.in_stock ? `₹${p.price.toFixed(2)}` : "Out of stock"}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {product && (
            <Card className="space-y-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <Price price={product.price} mrp={product.mrp} size="lg" />
                  <p className="mt-0.5 text-xs text-muted">Inclusive of all taxes · {product.pack_size}</p>
                </div>
                <p className={cn("text-sm font-semibold", product.in_stock ? "text-emerald-600" : "text-rose-600")}>
                  {product.in_stock ? (product.available_quantity <= 10 ? `Only ${product.available_quantity} left` : "In stock") : "Out of stock"}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <QuantityStepper value={quantity} onChange={setQuantity} max={Math.max(1, maxQty)} disabled={!product.in_stock} />
                <Button
                  size="lg"
                  className="flex-1 sm:flex-none"
                  disabled={!product.in_stock}
                  loading={add.isPending}
                  leftIcon={<ShoppingCart className="h-5 w-5" />}
                  onClick={() => add.mutate({ productId: product.id, quantity })}
                >
                  Add to cart
                </Button>
              </div>
              {medicine.prescription_required && (
                <Alert tone="warning" title="This medicine needs a valid prescription">
                  You can add it to your cart now. Before checkout, upload and confirm the prescription it is written on.{" "}
                  <Link to="/prescriptions/upload" className="inline-flex items-center gap-1 font-semibold underline">
                    <FileUp className="h-3.5 w-3.5" /> Upload prescription
                  </Link>
                </Alert>
              )}
            </Card>
          )}

          <Card>
            <h2 className="text-base font-semibold text-ink">Product details</h2>
            <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              {details
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 border-b border-line py-1.5 sm:border-0 sm:py-0">
                    <dt className="text-muted">{k}</dt>
                    <dd className="text-right font-medium text-ink">{v}</dd>
                  </div>
                ))}
            </dl>
            {medicine.description && <p className="mt-4 text-sm leading-relaxed text-ink">{medicine.description}</p>}
            <p className="mt-4 flex items-start gap-2 text-xs text-muted">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              Product information is for reference only. Follow your doctor's advice and the instructions on the pack.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}

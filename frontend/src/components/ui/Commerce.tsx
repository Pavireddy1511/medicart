import { Minus, Pill, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/Feedback";
import type { Medicine } from "@/types";
import { categoryIcons, cheapestProduct } from "@/utils/catalogue";
import { cn } from "@/utils/cn";
import { formatPrice } from "@/utils/format";

export function CategoryIcon({ icon, className }: { icon: string | null | undefined; className?: string }) {
  const Icon = (icon && categoryIcons[icon]) || Pill;
  return <Icon className={className} />;
}

const tints = [
  "from-brand-100 to-brand-50 text-brand-500",
  "from-sky-100 to-sky-50 text-sky-600",
  "from-emerald-100 to-emerald-50 text-emerald-600",
  "from-amber-100 to-amber-50 text-amber-600",
  "from-rose-100 to-rose-50 text-rose-500",
  "from-violet-100 to-violet-50 text-violet-600",
];

export function ProductImage({
  medicine,
  className,
  iconClassName = "h-10 w-10",
}: {
  medicine: Pick<Medicine, "medicine_name" | "image_url" | "category">;
  className?: string;
  iconClassName?: string;
}) {
  if (medicine.image_url) {
    return (
      <img
        src={medicine.image_url}
        alt={medicine.medicine_name}
        loading="lazy"
        className={cn("h-full w-full object-cover", className)}
      />
    );
  }
  const tint = tints[(medicine.category?.id ?? 0) % tints.length];
  return (
    <div className={cn("flex h-full w-full items-center justify-center bg-gradient-to-br", tint, className)} aria-hidden="true">
      <CategoryIcon icon={medicine.category?.icon} className={iconClassName} />
    </div>
  );
}

export function Price({
  price,
  mrp,
  size = "md",
  className,
}: {
  price: number;
  mrp?: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const showMrp = typeof mrp === "number" && mrp > price;
  const main = size === "lg" ? "text-2xl" : size === "sm" ? "text-sm" : "text-base";
  return (
    <span className={cn("inline-flex flex-wrap items-baseline gap-x-2", className)}>
      <span className={cn("font-bold text-ink", main)}>{formatPrice(price)}</span>
      {showMrp && <span className="text-xs text-muted line-through">{formatPrice(mrp)}</span>}
    </span>
  );
}

export function ProductCard({
  medicine,
  onAdd,
  adding,
}: {
  medicine: Medicine;
  onAdd?: (productId: number) => void;
  adding?: boolean;
}) {
  const product = cheapestProduct(medicine);
  const inStock = Boolean(product?.in_stock);
  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-card transition-shadow hover:shadow-pop">
      <Link to={`/medicines/${medicine.id}`} className="relative block aspect-[4/3] overflow-hidden bg-surface">
        <ProductImage medicine={medicine} />
        <div className="absolute left-2 top-2 flex flex-col gap-1">
          {product && product.discount_percent > 0 && <Badge tone="success">{product.discount_percent}% off</Badge>}
          {medicine.prescription_required && <Badge tone="warning">Rx</Badge>}
        </div>
      </Link>
      <div className="flex flex-1 flex-col gap-1 p-3.5">
        <Link to={`/medicines/${medicine.id}`} className="line-clamp-2 text-sm font-semibold text-ink hover:text-brand-600">
          {medicine.medicine_name}
        </Link>
        <p className="truncate text-xs text-muted" title={medicine.generic_name ?? undefined}>
          {[medicine.generic_name ?? medicine.brand_name, product?.pack_size].filter(Boolean).join(" · ")}
        </p>
        <div className="mt-auto flex items-end justify-between gap-2 pt-2">
          {product ? <Price price={product.price} mrp={product.mrp} /> : <span className="text-sm text-muted">Unavailable</span>}
          {onAdd && product && (
            <button
              type="button"
              disabled={!inStock || adding}
              onClick={() => onAdd(product.id)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                inStock ? "bg-brand-500 text-white hover:bg-brand-600" : "bg-surface text-muted",
              )}
            >
              {inStock ? "Add" : "Out of stock"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

export function QuantityStepper({
  value,
  onChange,
  min = 1,
  max = 20,
  disabled,
  size = "md",
}: {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  size?: "sm" | "md";
}) {
  const h = size === "sm" ? "h-8" : "h-10";
  return (
    <div className={cn("inline-flex items-center rounded-xl border border-line bg-white", h)}>
      <button
        type="button"
        aria-label="Decrease quantity"
        disabled={disabled || value <= min}
        onClick={() => onChange(value - 1)}
        className="flex h-full w-9 items-center justify-center rounded-l-xl text-brand-600 hover:bg-brand-50 disabled:text-muted/50"
      >
        <Minus className="h-4 w-4" />
      </button>
      <span className="w-8 text-center text-sm font-semibold tabular-nums">{value}</span>
      <button
        type="button"
        aria-label="Increase quantity"
        disabled={disabled || value >= max}
        onClick={() => onChange(value + 1)}
        className="flex h-full w-9 items-center justify-center rounded-r-xl text-brand-600 hover:bg-brand-50 disabled:text-muted/50"
      >
        <Plus className="h-4 w-4" />
      </button>
    </div>
  );
}

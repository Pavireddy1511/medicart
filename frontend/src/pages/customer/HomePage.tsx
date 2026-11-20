import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowRight, FileUp, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { LinkButton } from "@/components/ui/Button";
import { CategoryIcon, ProductCard } from "@/components/ui/Commerce";
import { Skeleton } from "@/components/ui/Feedback";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/hooks/useCart";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { catalogueApi } from "@/services/api";
import type { Medicine } from "@/types";
import { recentlyViewed } from "@/utils/storage";

function Section({
  title,
  subtitle,
  link,
  children,
}: {
  title: string;
  subtitle?: string;
  link?: { to: string; label: string };
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-ink">{title}</h2>
          {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
        </div>
        {link && (
          <Link to={link.to} className="inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:underline">
            {link.label} <ArrowRight className="h-4 w-4" />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

function Grid({ items, onAdd, adding }: { items: Medicine[]; onAdd: (id: number) => void; adding: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {items.map((m) => (
        <ProductCard key={m.id} medicine={m} onAdd={onAdd} adding={adding} />
      ))}
    </div>
  );
}

function GridSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="aspect-[3/4]" />
      ))}
    </div>
  );
}

export default function HomePage() {
  useDocumentTitle("Home");
  const { user } = useAuth();
  const { add } = useCart();
  const { data, isLoading } = useQuery({ queryKey: ["home"], queryFn: catalogueApi.home, staleTime: 5 * 60_000 });

  const recentIds = recentlyViewed.get();
  const recent = useQueries({
    queries: recentIds.slice(0, 4).map((id) => ({
      queryKey: ["medicine", id],
      queryFn: () => catalogueApi.medicine(id),
      staleTime: 5 * 60_000,
      retry: 0,
    })),
  });
  const recentItems = recent.map((q) => q.data).filter((m): m is NonNullable<typeof m> => Boolean(m));

  const onAdd = (productId: number) => add.mutate({ productId });
  const canShop = user?.role === "customer";

  return (
    <div className="space-y-10">
      <section className="relative overflow-hidden rounded-3xl bg-brand-900 px-6 py-8 text-white sm:px-10 sm:py-12">
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-brand-500/40 blur-3xl" />
        <div className="absolute -bottom-20 right-24 h-56 w-56 rounded-full bg-brand-400/30 blur-3xl" />
        <div className="relative max-w-xl">
          <p className="text-sm font-semibold text-brand-200">Hi {user?.full_name.split(" ")[0]}</p>
          <h1 className="mt-1 text-2xl font-bold leading-tight sm:text-3xl">Have a prescription? Upload it, we read it.</h1>
          <p className="mt-3 text-sm text-brand-100 sm:text-base">
            Upload a photo or PDF. We pull out the medicines, you check every line, and one click puts them in your
            cart. A pharmacist review is there if you want one.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <LinkButton to="/prescriptions/upload" size="lg" variant="inverse" leftIcon={<FileUp className="h-5 w-5" />}>
              Upload prescription
            </LinkButton>
            <LinkButton to="/medicines" size="lg" variant="inverse-ghost">
              Browse all products
            </LinkButton>
          </div>
          <p className="mt-5 inline-flex items-center gap-2 text-xs text-brand-200">
            <ShieldCheck className="h-4 w-4" /> Images are processed for this session only and never stored.
          </p>
        </div>
      </section>

      <Section title="Shop by category">
        {isLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {data?.categories.map((c) => (
              <Link
                key={c.id}
                to={`/medicines?category=${c.slug}`}
                className="group flex flex-col items-center gap-2 rounded-2xl border border-line bg-white p-4 text-center shadow-card transition-colors hover:border-brand-300 hover:bg-brand-50"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-100 text-brand-600 group-hover:bg-brand-500 group-hover:text-white">
                  <CategoryIcon icon={c.icon} className="h-5 w-5" />
                </span>
                <span className="text-sm font-semibold text-ink">{c.name}</span>
                <span className="text-xs text-muted">{c.medicine_count} items</span>
              </Link>
            ))}
          </div>
        )}
      </Section>

      {(isLoading || (data?.deals.length ?? 0) > 0) && (
        <Section title="Deals of the day" subtitle="Biggest discounts in stock right now" link={{ to: "/medicines?sort=price_asc", label: "See all" }}>
          {isLoading || !data ? <GridSkeleton /> : <Grid items={data.deals} onAdd={onAdd} adding={add.isPending} />}
        </Section>
      )}

      <Section title="Featured products" subtitle="No prescription needed" link={{ to: "/medicines?prescription_required=false", label: "Browse" }}>
        {isLoading || !data ? <GridSkeleton /> : <Grid items={data.featured} onAdd={canShop ? onAdd : () => undefined} adding={add.isPending} />}
      </Section>

      <Section title="Popular with customers" link={{ to: "/medicines", label: "View catalogue" }}>
        {isLoading || !data ? <GridSkeleton /> : <Grid items={data.popular} onAdd={onAdd} adding={add.isPending} />}
      </Section>

      {recentItems.length > 0 && (
        <Section title="Recently viewed">
          <Grid items={recentItems} onAdd={onAdd} adding={add.isPending} />
        </Section>
      )}
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  FileUp,
  LayoutDashboard,
  LogOut,
  MapPin,
  Menu,
  Package,
  Search,
  ShoppingCart,
  Stethoscope,
  Tag,
  User as UserIcon,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { Logo } from "@/components/Brand";
import { CategoryIcon } from "@/components/ui/Commerce";
import { useAuth } from "@/context/AuthContext";
import { useCart } from "@/hooks/useCart";
import { catalogueApi } from "@/services/api";
import type { Category, Medicine } from "@/types";
import { cn } from "@/utils/cn";

function SearchBar({ className }: { className?: string }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const urlQuery = location.pathname === "/medicines" ? (params.get("q") ?? "") : null;
  const [value, setValue] = useState(urlQuery ?? "");
  const [syncedQuery, setSyncedQuery] = useState(urlQuery);

  // Keep the box in step with the URL when the user navigates (back button, category links).
  if (urlQuery !== null && urlQuery !== syncedQuery) {
    setSyncedQuery(urlQuery);
    setValue(urlQuery);
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    navigate(q ? `/medicines?q=${encodeURIComponent(q)}` : "/medicines");
  };

  return (
    <form onSubmit={submit} role="search" className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search medicines, brands, health products"
        aria-label="Search medicines"
        className="h-11 w-full rounded-xl border border-line bg-surface pl-10 pr-4 text-sm text-ink placeholder:text-muted/80 focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-200"
      />
    </form>
  );
}

function ProfileMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!user) return null;
  const initials = user.full_name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const item = "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink hover:bg-brand-50";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-xl p-1 pr-2 hover:bg-brand-50"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
          {initials || <UserIcon className="h-4 w-4" />}
        </span>
        <span className="hidden max-w-[120px] truncate text-sm font-medium text-ink md:block">{user.full_name}</span>
        <ChevronDown className="hidden h-4 w-4 text-muted md:block" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-60 rounded-xl border border-line bg-white p-1.5 shadow-pop">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-semibold text-ink">{user.full_name}</p>
            <p className="text-xs text-muted">+91 {user.mobile_number}</p>
          </div>
          <div className="my-1 border-t border-line" />
          <Link to="/orders" className={item} onClick={() => setOpen(false)}>
            <Package className="h-4 w-4 text-muted" /> My orders
          </Link>
          <Link to="/prescriptions" className={item} onClick={() => setOpen(false)}>
            <FileUp className="h-4 w-4 text-muted" /> My prescriptions
          </Link>
          <Link to="/addresses" className={item} onClick={() => setOpen(false)}>
            <MapPin className="h-4 w-4 text-muted" /> Saved addresses
          </Link>
          <Link to="/profile" className={item} onClick={() => setOpen(false)}>
            <UserIcon className="h-4 w-4 text-muted" /> Profile & security
          </Link>
          {(user.role === "pharmacist" || user.role === "admin") && (
            <>
              <div className="my-1 border-t border-line" />
              <Link to="/pharmacist" className={item} onClick={() => setOpen(false)}>
                <Stethoscope className="h-4 w-4 text-muted" /> Pharmacist desk
              </Link>
            </>
          )}
          {user.role === "admin" && (
            <Link to="/admin" className={item} onClick={() => setOpen(false)}>
              <LayoutDashboard className="h-4 w-4 text-muted" /> Admin dashboard
            </Link>
          )}
          <div className="my-1 border-t border-line" />
          <button
            type="button"
            className={cn(item, "w-full text-rose-600 hover:bg-rose-50")}
            onClick={async () => {
              setOpen(false);
              await logout();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function Header({ onMenu }: { onMenu: () => void }) {
  const { itemCount } = useCart();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onMenu}
          className="rounded-lg p-2 text-ink hover:bg-brand-50 lg:hidden"
          aria-label="Open categories"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Logo />
        <SearchBar className="mx-auto hidden w-full max-w-xl md:block" />
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <Link
            to="/prescriptions/upload"
            className="hidden h-10 items-center gap-2 rounded-xl bg-brand-100 px-3 text-sm font-semibold text-brand-700 hover:bg-brand-200 sm:inline-flex"
          >
            <FileUp className="h-4 w-4" /> Upload prescription
          </Link>
          <Link
            to="/prescriptions/upload"
            className="rounded-xl p-2 text-brand-700 hover:bg-brand-50 sm:hidden"
            aria-label="Upload prescription"
          >
            <FileUp className="h-5 w-5" />
          </Link>
          <Link to="/cart" className="relative rounded-xl p-2 text-ink hover:bg-brand-50" aria-label={`Cart, ${itemCount} items`}>
            <ShoppingCart className="h-5 w-5" />
            {itemCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-500 px-1 text-[11px] font-bold text-white">
                {itemCount > 99 ? "99+" : itemCount}
              </span>
            )}
          </Link>
          <ProfileMenu />
        </div>
      </div>
      <div className="px-4 pb-3 md:hidden">
        <SearchBar />
      </div>
    </header>
  );
}

function OfferBar({ deals }: { deals: Medicine[] }) {
  const offers = [
    "Free delivery on orders above ₹499",
    "Cash on delivery available on every order",
    "Upload a prescription and get it pharmacist-checked",
    ...deals.slice(0, 4).map((m) => {
      const best = Math.max(...m.products.map((p) => p.discount_percent));
      return `${best}% off ${m.medicine_name}`;
    }),
  ];
  const track = [...offers, ...offers];
  return (
    <div className="overflow-hidden border-b border-brand-200 bg-brand-500 text-white" aria-label="Current offers">
      <div className="ticker-track flex w-max items-center gap-10 py-2 text-xs font-medium sm:text-sm">
        {track.map((text, i) => (
          <span key={i} className="inline-flex items-center gap-2 whitespace-nowrap">
            <Tag className="h-3.5 w-3.5 text-brand-100" /> {text}
          </span>
        ))}
      </div>
    </div>
  );
}

function CategoryNav({ categories, onNavigate }: { categories: Category[]; onNavigate?: () => void }) {
  const [params] = useSearchParams();
  const location = useLocation();
  const active = location.pathname === "/medicines" ? params.get("category") : null;
  const base = "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors";
  return (
    <nav aria-label="Categories" className="space-y-1">
      <NavLink
        to="/medicines"
        onClick={onNavigate}
        className={({ isActive }) =>
          cn(base, isActive && !active ? "bg-brand-500 text-white" : "text-ink hover:bg-brand-50")
        }
        end
      >
        <Search className="h-4 w-4" /> All products
      </NavLink>
      {categories.map((c) => (
        <Link
          key={c.id}
          to={`/medicines?category=${c.slug}`}
          onClick={onNavigate}
          className={cn(base, active === c.slug ? "bg-brand-500 text-white" : "text-ink hover:bg-brand-50")}
        >
          <CategoryIcon icon={c.icon} className="h-4 w-4" />
          <span className="flex-1 truncate">{c.name}</span>
          <span className={cn("text-xs", active === c.slug ? "text-brand-100" : "text-muted")}>{c.medicine_count}</span>
        </Link>
      ))}
    </nav>
  );
}

export function CustomerLayout() {
  const [drawer, setDrawer] = useState(false);
  const location = useLocation();
  const [drawerLocation, setDrawerLocation] = useState(location.key);
  const { data: home } = useQuery({ queryKey: ["home"], queryFn: catalogueApi.home, staleTime: 5 * 60_000 });
  const categories = home?.categories ?? [];

  if (drawerLocation !== location.key) {
    setDrawerLocation(location.key);
    if (drawer) setDrawer(false);
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <Header onMenu={() => setDrawer(true)} />
      <OfferBar deals={home?.deals ?? []} />

      <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:grid lg:grid-cols-[232px_minmax(0,1fr)] lg:gap-8 lg:px-8">
        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-2xl border border-line bg-white p-3 shadow-card">
            <p className="px-3 pb-2 pt-1 text-xs font-semibold uppercase tracking-wide text-muted">Shop by category</p>
            <CategoryNav categories={categories} />
          </div>
        </aside>
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>MediCart is a final-year student project. It is not a licensed pharmacy and processes no real payments.</p>
          <p>Prescription text is read by OCR and a third-party AI model, then checked by you. A pharmacist review is available on request.</p>
        </div>
      </footer>

      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Categories">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 flex w-80 max-w-[85vw] flex-col bg-white shadow-pop">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <Logo />
              <button type="button" onClick={() => setDrawer(false)} className="rounded-lg p-2 hover:bg-brand-50" aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="scrollbar-thin flex-1 overflow-y-auto p-3">
              <CategoryNav categories={categories} onNavigate={() => setDrawer(false)} />
              <div className="my-3 border-t border-line" />
              <Link
                to="/prescriptions/upload"
                className="flex items-center gap-3 rounded-xl bg-brand-100 px-3 py-2.5 text-sm font-semibold text-brand-700"
              >
                <FileUp className="h-4 w-4" /> Upload prescription
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

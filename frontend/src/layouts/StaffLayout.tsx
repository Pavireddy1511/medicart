import { useQuery } from "@tanstack/react-query";
import {
  ClipboardList,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Pill,
  Store,
  Tags,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Logo } from "@/components/Brand";
import { useAuth } from "@/context/AuthContext";
import { pharmacistApi } from "@/services/api";
import { cn } from "@/utils/cn";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  badge?: number;
}

export function StaffLayout({ area }: { area: "pharmacist" | "admin" }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [openedAt, setOpenedAt] = useState(location.key);

  const { data: summary } = useQuery({
    queryKey: ["pharmacist", "summary"],
    queryFn: pharmacistApi.summary,
    refetchInterval: 60_000,
  });

  if (openedAt !== location.key) {
    setOpenedAt(location.key);
    if (open) setOpen(false);
  }

  const pharmacistNav: NavItem[] = [
    { to: "/pharmacist", label: "Verification queue", icon: ClipboardList, end: true, badge: summary?.pending },
    { to: "/pharmacist/history", label: "Verification history", icon: History },
  ];
  const adminNav: NavItem[] = [
    { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/admin/medicines", label: "Medicines & stock", icon: Pill },
    { to: "/admin/categories", label: "Categories", icon: Tags },
    { to: "/admin/orders", label: "Orders", icon: Package },
    { to: "/admin/prescriptions", label: "Prescriptions", icon: FileText },
    { to: "/admin/users", label: "Customers & staff", icon: Users },
  ];
  const nav = area === "admin" ? adminNav : pharmacistNav;
  const title = area === "admin" ? "Admin" : "Pharmacist desk";

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-4">
        <Logo to={area === "admin" ? "/admin" : "/pharmacist"} />
        <button type="button" className="rounded-lg p-2 hover:bg-brand-50 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X className="h-5 w-5" />
        </button>
      </div>
      <p className="px-6 pb-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
      <nav className="flex-1 space-y-1 px-3">
        {nav.map(({ to, label, icon: Icon, end, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-brand-500 text-white" : "text-ink hover:bg-brand-50",
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span className="flex-1">{label}</span>
            {badge ? (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">{badge}</span>
            ) : null}
          </NavLink>
        ))}
        {user?.role === "admin" && area === "pharmacist" && (
          <NavLink to="/admin" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink hover:bg-brand-50">
            <LayoutDashboard className="h-4 w-4" /> Admin dashboard
          </NavLink>
        )}
        {(user?.role === "admin" || user?.role === "pharmacist") && area === "admin" && (
          <NavLink to="/pharmacist" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink hover:bg-brand-50">
            <ClipboardList className="h-4 w-4" /> Pharmacist desk
          </NavLink>
        )}
      </nav>
      <div className="border-t border-line p-3">
        <NavLink to="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink hover:bg-brand-50">
          <Store className="h-4 w-4" /> Go to storefront
        </NavLink>
        <button
          type="button"
          onClick={async () => {
            await logout();
            navigate("/login");
          }}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-rose-600 hover:bg-rose-50"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="hidden border-r border-line bg-white lg:block">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 bg-white shadow-pop">{sidebar}</div>
        </div>
      )}
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-line bg-white/95 px-4 backdrop-blur sm:px-6">
          <button type="button" className="rounded-lg p-2 hover:bg-brand-50 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="lg:hidden">
            <Logo iconOnly to={area === "admin" ? "/admin" : "/pharmacist"} />
          </div>
          <p className="text-sm font-semibold text-muted">{title}</p>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-semibold text-ink">{user?.full_name}</p>
              <p className="text-xs capitalize text-muted">{user?.role}</p>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
              {user?.full_name?.[0]?.toUpperCase()}
            </span>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

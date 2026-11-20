import { FileSearch, ShieldCheck, Truck } from "lucide-react";
import { Outlet } from "react-router-dom";

import { Logo } from "@/components/Brand";

const points = [
  { icon: FileSearch, title: "Upload a prescription", text: "Photo or PDF. We read it and let you check every line." },
  { icon: ShieldCheck, title: "Pharmacist on call", text: "Ask a pharmacist to review any prescription before your order ships." },
  { icon: Truck, title: "Doorstep delivery", text: "Free delivery on orders above ₹499. Cash on delivery available." },
];

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-surface lg:grid lg:grid-cols-[1.1fr_1fr]">
      <aside className="hidden bg-brand-900 text-white lg:flex lg:flex-col lg:justify-between lg:px-14 lg:py-12">
        <Logo to="/login" className="[&_span:last-child]:text-white" />
        <div className="max-w-md">
          <h2 className="text-3xl font-bold leading-tight">Your neighbourhood pharmacy, online.</h2>
          <p className="mt-3 text-brand-200">
            Medicines, personal care and daily essentials delivered to your door, with prescriptions checked by a
            pharmacist.
          </p>
          <ul className="mt-10 space-y-6">
            {points.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <Icon className="h-5 w-5 text-brand-200" />
                </span>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="text-sm text-brand-200">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-brand-300">Student project demo. Not a licensed pharmacy.</p>
      </aside>
      <main className="flex min-h-screen flex-col items-center justify-center px-4 py-10 sm:px-6">
        <div className="mb-8 lg:hidden">
          <Logo to="/login" />
        </div>
        <div className="w-full max-w-md rounded-2xl border border-line bg-white p-6 shadow-card sm:p-8">
          <Outlet />
        </div>
        <p className="mt-6 text-center text-xs text-muted lg:hidden">Student project demo. Not a licensed pharmacy.</p>
      </main>
    </div>
  );
}

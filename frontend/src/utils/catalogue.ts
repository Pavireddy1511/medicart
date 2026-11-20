import { Droplets, HeartPulse, Pill, ShoppingBasket, Sparkles, Stethoscope, type LucideIcon } from "lucide-react";

import type { Medicine } from "@/types";

export const categoryIcons: Record<string, LucideIcon> = {
  pill: Pill,
  stethoscope: Stethoscope,
  sparkles: Sparkles,
  droplets: Droplets,
  "shopping-basket": ShoppingBasket,
  "heart-pulse": HeartPulse,
};

export function cheapestProduct(medicine: Medicine) {
  const active = medicine.products.filter((p) => p.is_active);
  return [...active].sort((a, b) => a.price - b.price)[0] ?? null;
}

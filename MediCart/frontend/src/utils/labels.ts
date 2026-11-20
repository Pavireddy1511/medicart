import type { OrderStatus, VerificationStatus } from "@/types";

export const orderStatusLabel: Record<OrderStatus, string> = {
  placed: "Order placed",
  verification_pending: "Awaiting pharmacist",
  verified: "Pharmacist verified",
  processing: "Processing",
  packed: "Packed",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export const verificationLabel: Record<VerificationStatus, string> = {
  not_required: "No verification needed",
  pending: "Pharmacist review pending",
  approved: "Pharmacist approved",
  rejected: "Rejected by pharmacist",
  clarification_requested: "Clarification requested",
};

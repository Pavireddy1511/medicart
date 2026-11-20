export type Role = "customer" | "pharmacist" | "admin";

export interface User {
  id: number;
  full_name: string;
  mobile_number: string;
  email: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
}

export interface FieldError {
  field: string;
  message: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  sort_order: number;
  medicine_count: number;
}

export interface Product {
  id: number;
  sku: string;
  pack_size: string;
  mrp: number;
  price: number;
  discount_percent: number;
  is_active: boolean;
  available_quantity: number;
  in_stock: boolean;
}

export interface Medicine {
  id: number;
  medicine_name: string;
  generic_name: string | null;
  brand_name: string | null;
  strength: string | null;
  formulation: string | null;
  manufacturer: string | null;
  prescription_required: boolean;
  composition: string | null;
  image_url: string | null;
  is_active: boolean;
  category: Category | null;
  products: Product[];
}

export interface MedicineDetail extends Medicine {
  description: string | null;
  created_at: string;
}

export type SortOption = "relevance" | "price_asc" | "price_desc" | "name_asc" | "name_desc" | "newest";

export interface MedicineQuery {
  q?: string;
  category?: string;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  prescription_required?: boolean;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

export interface HomeFeed {
  categories: Category[];
  featured: Medicine[];
  deals: Medicine[];
  popular: Medicine[];
}

export interface CartProduct {
  id: number;
  sku: string;
  pack_size: string;
  mrp: number;
  price: number;
  available_quantity: number;
  is_active: boolean;
  medicine_id: number;
  medicine_name: string;
  brand_name: string | null;
  strength: string | null;
  formulation: string | null;
  prescription_required: boolean;
  image_url: string | null;
}

export interface CartItem {
  id: number;
  product_id: number;
  quantity: number;
  price_snapshot: number;
  unit_price: number;
  line_total: number;
  price_changed: boolean;
  in_stock: boolean;
  product: CartProduct;
}

export interface Cart {
  id: number;
  items: CartItem[];
  item_count: number;
  subtotal: number;
  delivery_charge: number;
  total: number;
  free_delivery_above: number;
  requires_prescription: boolean;
  has_unavailable_items: boolean;
}

export type AddressType = "home" | "work" | "other";

export interface Address {
  id: number;
  recipient_name: string;
  mobile_number: string;
  house_building: string;
  street: string;
  landmark: string | null;
  city: string;
  state: string;
  pincode: string;
  address_type: AddressType;
  is_default: boolean;
  created_at: string;
}

export type AddressInput = Omit<Address, "id" | "created_at">;

export type OrderStatus =
  | "placed"
  | "verification_pending"
  | "verified"
  | "processing"
  | "packed"
  | "shipped"
  | "delivered"
  | "cancelled";

export type PaymentMethod = "cod" | "simulated_online";

export interface OrderItem {
  id: number;
  product_id: number | null;
  product_name_snapshot: string;
  pack_size_snapshot: string | null;
  prescription_required: boolean;
  quantity: number;
  price_snapshot: number;
  subtotal: number;
}

export interface Payment {
  id: number;
  payment_method: string;
  transaction_reference: string | null;
  payment_status: string;
  amount: number;
  created_at: string;
}

export interface Shipment {
  id: number;
  tracking_reference: string | null;
  shipment_status: string;
  updated_at: string;
}

export interface OrderSummary {
  id: number;
  order_number: string;
  order_status: OrderStatus;
  payment_status: string;
  payment_method: PaymentMethod;
  order_total: number;
  item_count: number;
  created_at: string;
  delivered_at: string | null;
  items: OrderItem[];
}

export interface OrderDetail extends OrderSummary {
  subtotal: number;
  delivery_charge: number;
  address_snapshot: Omit<Address, "id" | "created_at" | "is_default">;
  prescription_id: number | null;
  cancellation_reason: string | null;
  payments: Payment[];
  shipment: Shipment | null;
  updated_at: string;
  can_cancel: boolean;
  allowed_next_statuses: OrderStatus[];
}

export type MatchStatus = "exact" | "possible" | "uncertain" | "none";
export type VerificationStatus =
  | "not_required"
  | "pending"
  | "approved"
  | "rejected"
  | "clarification_requested";

export interface MedicineRef {
  id: number;
  medicine_name: string;
  generic_name: string | null;
  brand_name: string | null;
  strength: string | null;
  formulation: string | null;
  prescription_required: boolean;
  composition: string | null;
  image_url: string | null;
  products: Product[];
}

export interface Candidate {
  medicine_id: number;
  medicine_name: string;
  brand_name: string | null;
  generic_name: string | null;
  strength: string | null;
  formulation: string | null;
  prescription_required: boolean;
  score: number;
  matched_on: string;
}

export interface PrescriptionItem {
  id: number;
  extracted_name: string;
  original_text: string | null;
  strength_text: string | null;
  formulation_text: string | null;
  dosage_text: string | null;
  frequency_text: string | null;
  duration_text: string | null;
  uncertainty_status: "clear" | "uncertain";
  uncertain_fields: string[];
  match_status: MatchStatus;
  matched_medicine: MedicineRef | null;
  candidates: Candidate[];
  user_confirmed: boolean;
  user_edited: boolean;
  included: boolean;
  can_add_to_cart: boolean;
  blocked_reason: string | null;
}

export interface Verification {
  id: number;
  verification_status: string;
  notes: string | null;
  verified_at: string;
  pharmacist_name: string | null;
}

export interface Prescription {
  id: number;
  processing_status: string;
  document_type: "printed" | "handwritten" | "unknown";
  source_format: "image" | "pdf";
  page_count: number;
  ocr_engine: string | null;
  ocr_confidence: number | null;
  ai_review_status: "completed" | "fallback" | "unavailable" | "skipped";
  ai_model: string | null;
  user_confirmation_status: "pending" | "confirmed";
  pharmacist_verification_status: VerificationStatus;
  customer_notes: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
  items: PrescriptionItem[];
  verifications: Verification[];
  warnings: string[];
  show_handwriting_disclaimer: boolean;
  handwriting_disclaimer: string | null;
  original_image_retained: boolean;
}

export interface ProcessingInfo {
  ocr_engine: string | null;
  ocr_available: boolean;
  handwriting_engine_used: boolean;
  ai_source: string;
  elapsed_ms: number;
  preprocessing_steps: string[];
  notes: string[];
}

export interface AnalyseResponse {
  prescription: Prescription;
  extracted_text: string;
  preview_images: string[];
  processing: ProcessingInfo;
}

export interface ConfirmItemInput {
  item_id: number;
  extracted_name: string;
  strength_text?: string | null;
  formulation_text?: string | null;
  dosage_text?: string | null;
  frequency_text?: string | null;
  duration_text?: string | null;
  matched_medicine_id?: number | null;
  included: boolean;
}

export interface NewItemInput {
  extracted_name: string;
  strength_text?: string | null;
  formulation_text?: string | null;
  dosage_text?: string | null;
  frequency_text?: string | null;
  duration_text?: string | null;
  matched_medicine_id?: number | null;
}

export interface ConfirmRequest {
  prescription_id: number;
  items: ConfirmItemInput[];
  new_items: NewItemInput[];
  customer_notes?: string | null;
  request_pharmacist_review?: boolean;
  add_to_cart?: boolean;
}

export interface ConfirmResponse extends Prescription {
  cart_added: { medicine_name: string; product_id: number; pack_size: string; quantity: number }[];
  cart_skipped: { name: string; reason: string }[];
}

export interface PrescriptionListItem {
  id: number;
  processing_status: string;
  document_type: string;
  user_confirmation_status: string;
  pharmacist_verification_status: VerificationStatus;
  ai_review_status: string;
  created_at: string;
  item_count: number;
}

export interface VerificationRequestSummary {
  prescription_id: number;
  customer_name: string;
  customer_mobile_masked: string;
  document_type: string;
  ai_review_status: string;
  ocr_confidence: number | null;
  user_confirmation_status: string;
  pharmacist_verification_status: VerificationStatus;
  item_count: number;
  rx_item_count: number;
  uncertain_item_count: number;
  customer_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface VerificationDetail extends Prescription {
  customer_name: string;
  customer_mobile_masked: string;
  extracted_text: string | null;
  linked_order_numbers: string[];
}

export interface HistoryEntry extends Verification {
  prescription_id: number;
}

// admin
export interface PrescriptionStats {
  total: number;
  awaiting_confirmation: number;
  pending_verification: number;
  approved: number;
  rejected: number;
  clarification_requested: number;
  uncertain_items: number;
  ai_fallback: number;
}

export interface AdminOrder extends OrderSummary {
  customer_name: string;
  customer_mobile: string;
  allowed_next_statuses: OrderStatus[];
}

export interface Dashboard {
  total_customers: number;
  total_medicines: number;
  total_products: number;
  total_orders: number;
  pending_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  simulated_revenue: number;
  prescriptions: PrescriptionStats;
  recent_orders: AdminOrder[];
  low_stock: { product_id: number; medicine_name: string; pack_size: string; available_quantity: number }[];
  orders_by_status: Record<string, number>;
}

export interface AdminUser extends User {
  order_count: number;
  updated_at: string;
}

export interface AdminCategory {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  sort_order: number;
  is_active: boolean;
  medicine_count: number;
}

export interface AdminProduct extends Product {
  inventory: { available_quantity: number; batch_number: string | null; expiry_date: string | null } | null;
}

export interface AdminMedicine {
  id: number;
  medicine_name: string;
  generic_name: string | null;
  brand_name: string | null;
  strength: string | null;
  formulation: string | null;
  manufacturer: string | null;
  description: string | null;
  prescription_required: boolean;
  category_id: number | null;
  image_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  products: AdminProduct[];
}

export interface ProductInput {
  sku?: string | null;
  pack_size: string;
  mrp: number;
  price: number;
  is_active: boolean;
  available_quantity: number;
  batch_number?: string | null;
  expiry_date?: string | null;
}

export interface MedicineInput {
  medicine_name: string;
  generic_name?: string | null;
  brand_name?: string | null;
  strength?: string | null;
  formulation?: string | null;
  manufacturer?: string | null;
  description?: string | null;
  prescription_required: boolean;
  category_id?: number | null;
  image_url?: string | null;
  is_active: boolean;
}

export interface AdminPrescriptionListItem {
  id: number;
  processing_status: string;
  document_type: string;
  ai_review_status: string;
  ocr_engine: string | null;
  ocr_confidence: number | null;
  user_confirmation_status: string;
  pharmacist_verification_status: VerificationStatus;
  created_at: string;
  item_count: number;
  uncertain_item_count: number;
  customer_name: string;
}

export interface AuditLogEntry {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  action: string;
  target_type: string;
  target_id: number | null;
  meta: Record<string, unknown> | null;
  created_at: string;
}

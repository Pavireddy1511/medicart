import type {
  Address,
  AddressInput,
  AdminCategory,
  AdminMedicine,
  AdminPrescriptionListItem,
  AdminOrder,
  AdminUser,
  AnalyseResponse,
  AuditLogEntry,
  Cart,
  Category,
  ConfirmRequest,
  ConfirmResponse,
  Dashboard,
  HistoryEntry,
  HomeFeed,
  Medicine,
  MedicineDetail,
  MedicineInput,
  MedicineQuery,
  OrderDetail,
  OrderStatus,
  OrderSummary,
  Page,
  PaymentMethod,
  Prescription,
  PrescriptionListItem,
  ProductInput,
  TokenResponse,
  User,
  VerificationDetail,
  VerificationRequestSummary,
} from "@/types";

import { request } from "./http";

export const authApi = {
  login: (mobile_number: string, password: string) =>
    request<TokenResponse>({ method: "POST", url: "/auth/login", data: { mobile_number, password } }),
  register: (data: {
    full_name: string;
    mobile_number: string;
    email?: string;
    password: string;
    confirm_password: string;
  }) => request<TokenResponse>({ method: "POST", url: "/auth/register", data }),
  me: () => request<User>({ method: "GET", url: "/auth/me" }),
  updateProfile: (data: { full_name?: string; email?: string | null }) =>
    request<User>({ method: "PUT", url: "/auth/me", data }),
  changePassword: (data: { current_password: string; new_password: string; confirm_password: string }) =>
    request<void>({ method: "POST", url: "/auth/change-password", data }),
  logout: () => request<void>({ method: "POST", url: "/auth/logout" }),
};

export const catalogueApi = {
  categories: () => request<Category[]>({ method: "GET", url: "/categories" }),
  home: () => request<HomeFeed>({ method: "GET", url: "/home" }),
  search: (params: MedicineQuery) => request<Page<Medicine>>({ method: "GET", url: "/medicines", params }),
  medicine: (id: number) => request<MedicineDetail>({ method: "GET", url: `/medicines/${id}` }),
};

export const cartApi = {
  get: () => request<Cart>({ method: "GET", url: "/cart" }),
  add: (product_id: number, quantity = 1) =>
    request<Cart>({ method: "POST", url: "/cart/items", data: { product_id, quantity } }),
  update: (itemId: number, quantity: number) =>
    request<Cart>({ method: "PUT", url: `/cart/items/${itemId}`, data: { quantity } }),
  remove: (itemId: number) => request<Cart>({ method: "DELETE", url: `/cart/items/${itemId}` }),
  clear: () => request<Cart>({ method: "DELETE", url: "/cart" }),
};

export const addressApi = {
  list: () => request<Address[]>({ method: "GET", url: "/addresses" }),
  create: (data: AddressInput) => request<Address>({ method: "POST", url: "/addresses", data }),
  update: (id: number, data: Partial<AddressInput>) =>
    request<Address>({ method: "PUT", url: `/addresses/${id}`, data }),
  remove: (id: number) => request<void>({ method: "DELETE", url: `/addresses/${id}` }),
  setDefault: (id: number) => request<Address>({ method: "POST", url: `/addresses/${id}/default` }),
};

export const orderApi = {
  list: () => request<OrderSummary[]>({ method: "GET", url: "/orders" }),
  get: (id: number) => request<OrderDetail>({ method: "GET", url: `/orders/${id}` }),
  place: (data: { address_id: number; payment_method: PaymentMethod; prescription_id?: number | null }) =>
    request<OrderDetail>({ method: "POST", url: "/orders", data }),
  cancel: (id: number, reason?: string) =>
    request<OrderDetail>({ method: "POST", url: `/orders/${id}/cancel`, data: { reason } }),
};

export const prescriptionApi = {
  analyse: (file: File, documentType: string | null, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    if (documentType) form.append("document_type", documentType);
    return request<AnalyseResponse>({
      method: "POST",
      url: "/prescriptions/analyse",
      data: form,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 180_000,
      onUploadProgress: (event) => {
        if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100));
      },
    });
  },
  confirm: (data: ConfirmRequest) =>
    request<ConfirmResponse>({ method: "POST", url: "/prescriptions/confirm", data }),
  list: () => request<PrescriptionListItem[]>({ method: "GET", url: "/prescriptions" }),
  get: (id: number) => request<Prescription>({ method: "GET", url: `/prescriptions/${id}` }),
  requestReview: (id: number, message?: string) =>
    request<Prescription>({ method: "POST", url: `/prescriptions/${id}/request-review`, data: { message } }),
};

export const pharmacistApi = {
  requests: (status?: string) =>
    request<VerificationRequestSummary[]>({
      method: "GET",
      url: "/pharmacist/verification-requests",
      params: status ? { status } : undefined,
    }),
  request: (id: number) =>
    request<VerificationDetail>({ method: "GET", url: `/pharmacist/verification-requests/${id}` }),
  decide: (data: { prescription_id: number; status: "approved" | "rejected" | "clarification_requested"; notes?: string }) =>
    request<VerificationDetail>({ method: "POST", url: "/pharmacist/verification", data }),
  history: (mine = false) => request<HistoryEntry[]>({ method: "GET", url: "/pharmacist/history", params: { mine } }),
  summary: () => request<{ pending: number }>({ method: "GET", url: "/pharmacist/summary" }),
};

export const adminApi = {
  dashboard: () => request<Dashboard>({ method: "GET", url: "/admin/dashboard" }),
  users: (params: { q?: string; role?: string; page?: number; page_size?: number }) =>
    request<Page<AdminUser>>({ method: "GET", url: "/admin/users", params }),
  updateUser: (id: number, data: { role?: string; is_active?: boolean }) =>
    request<AdminUser>({ method: "PATCH", url: `/admin/users/${id}`, data }),
  categories: () => request<AdminCategory[]>({ method: "GET", url: "/admin/categories" }),
  createCategory: (data: Partial<AdminCategory>) =>
    request<AdminCategory>({ method: "POST", url: "/admin/categories", data }),
  updateCategory: (id: number, data: Partial<AdminCategory>) =>
    request<AdminCategory>({ method: "PUT", url: `/admin/categories/${id}`, data }),
  deleteCategory: (id: number) => request<void>({ method: "DELETE", url: `/admin/categories/${id}` }),
  medicines: (params: { q?: string; category_id?: number; page?: number; page_size?: number }) =>
    request<Page<AdminMedicine>>({ method: "GET", url: "/admin/medicines", params }),
  medicine: (id: number) => request<AdminMedicine>({ method: "GET", url: `/admin/medicines/${id}` }),
  createMedicine: (data: MedicineInput & { products: ProductInput[] }) =>
    request<AdminMedicine>({ method: "POST", url: "/admin/medicines", data }),
  updateMedicine: (id: number, data: Partial<MedicineInput>) =>
    request<AdminMedicine>({ method: "PUT", url: `/admin/medicines/${id}`, data }),
  deleteMedicine: (id: number) => request<{ message: string }>({ method: "DELETE", url: `/admin/medicines/${id}` }),
  addProduct: (medicineId: number, data: ProductInput) =>
    request<AdminMedicine>({ method: "POST", url: `/admin/medicines/${medicineId}/products`, data }),
  updateProduct: (productId: number, data: Partial<Pick<ProductInput, "pack_size" | "mrp" | "price" | "is_active">>) =>
    request<AdminMedicine>({ method: "PUT", url: `/admin/products/${productId}`, data }),
  updateInventory: (
    productId: number,
    data: { available_quantity: number; batch_number?: string | null; expiry_date?: string | null },
  ) => request<AdminMedicine>({ method: "PUT", url: `/admin/products/${productId}/inventory`, data }),
  orders: (params: { status?: string; q?: string; page?: number; page_size?: number }) =>
    request<Page<AdminOrder>>({ method: "GET", url: "/admin/orders", params }),
  order: (id: number) => request<OrderDetail>({ method: "GET", url: `/admin/orders/${id}` }),
  updateOrderStatus: (id: number, data: { order_status: OrderStatus; tracking_reference?: string; note?: string }) =>
    request<OrderDetail>({ method: "PATCH", url: `/admin/orders/${id}/status`, data }),
  prescriptions: (params: { status?: string; page?: number; page_size?: number }) =>
    request<Page<AdminPrescriptionListItem>>({ method: "GET", url: "/admin/prescriptions", params }),
  prescription: (id: number) => request<VerificationDetail>({ method: "GET", url: `/admin/prescriptions/${id}` }),
  auditLogs: (limit = 100) => request<AuditLogEntry[]>({ method: "GET", url: "/admin/audit-logs", params: { limit } }),
};

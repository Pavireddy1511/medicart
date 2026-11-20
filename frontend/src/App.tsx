import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { Spinner } from "@/components/ui/Feedback";
import { homeFor, useAuth } from "@/context/AuthContext";
import { AuthLayout } from "@/layouts/AuthLayout";
import { CustomerLayout } from "@/layouts/CustomerLayout";
import { StaffLayout } from "@/layouts/StaffLayout";
import type { Role } from "@/types";

const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("@/pages/auth/RegisterPage"));

const HomePage = lazy(() => import("@/pages/customer/HomePage"));
const CataloguePage = lazy(() => import("@/pages/customer/CataloguePage"));
const ProductDetailPage = lazy(() => import("@/pages/customer/ProductDetailPage"));
const CartPage = lazy(() => import("@/pages/customer/CartPage"));
const CheckoutPage = lazy(() => import("@/pages/customer/CheckoutPage"));
const OrderSuccessPage = lazy(() => import("@/pages/customer/OrderSuccessPage"));
const OrdersPage = lazy(() => import("@/pages/customer/OrdersPage"));
const OrderDetailPage = lazy(() => import("@/pages/customer/OrderDetailPage"));
const ProfilePage = lazy(() => import("@/pages/customer/ProfilePage"));
const AddressesPage = lazy(() => import("@/pages/customer/AddressesPage"));
const PrescriptionUploadPage = lazy(() => import("@/pages/customer/PrescriptionUploadPage"));
const PrescriptionReviewPage = lazy(() => import("@/pages/customer/PrescriptionReviewPage"));
const PrescriptionsPage = lazy(() => import("@/pages/customer/PrescriptionsPage"));

const PharmacistQueuePage = lazy(() => import("@/pages/pharmacist/PharmacistQueuePage"));
const VerificationDetailPage = lazy(() => import("@/pages/pharmacist/VerificationDetailPage"));
const PharmacistHistoryPage = lazy(() => import("@/pages/pharmacist/PharmacistHistoryPage"));

const AdminDashboardPage = lazy(() => import("@/pages/admin/AdminDashboardPage"));
const AdminMedicinesPage = lazy(() => import("@/pages/admin/AdminMedicinesPage"));
const AdminMedicineFormPage = lazy(() => import("@/pages/admin/AdminMedicineFormPage"));
const AdminCategoriesPage = lazy(() => import("@/pages/admin/AdminCategoriesPage"));
const AdminUsersPage = lazy(() => import("@/pages/admin/AdminUsersPage"));
const AdminOrdersPage = lazy(() => import("@/pages/admin/AdminOrdersPage"));
const AdminOrderDetailPage = lazy(() => import("@/pages/admin/AdminOrderDetailPage"));
const AdminPrescriptionsPage = lazy(() => import("@/pages/admin/AdminPrescriptionsPage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

function RequireAuth({ roles, children }: { roles?: Role[]; children?: ReactNode }) {
  const { user, initialising } = useAuth();
  const location = useLocation();
  if (initialising) return <Spinner className="min-h-screen" label="Signing you in" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return children ? <>{children}</> : <Outlet />;
}

function RedirectIfAuthed() {
  const { user, initialising } = useAuth();
  if (initialising) return <Spinner className="min-h-screen" />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Suspense fallback={<Spinner className="min-h-screen" />}>
      <Routes>
        <Route element={<RedirectIfAuthed />}>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>
        </Route>

        <Route element={<RequireAuth roles={["customer", "pharmacist", "admin"]} />}>
          <Route element={<CustomerLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/medicines" element={<CataloguePage />} />
            <Route path="/medicines/:id" element={<ProductDetailPage />} />
            <Route path="/cart" element={<CartPage />} />
            <Route path="/checkout" element={<CheckoutPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:id" element={<OrderDetailPage />} />
            <Route path="/orders/:id/success" element={<OrderSuccessPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/addresses" element={<AddressesPage />} />
            <Route path="/prescriptions" element={<PrescriptionsPage />} />
            <Route path="/prescriptions/upload" element={<PrescriptionUploadPage />} />
            <Route path="/prescriptions/:id" element={<PrescriptionReviewPage />} />
          </Route>
        </Route>

        <Route element={<RequireAuth roles={["pharmacist", "admin"]} />}>
          <Route path="/pharmacist" element={<StaffLayout area="pharmacist" />}>
            <Route index element={<PharmacistQueuePage />} />
            <Route path="requests/:id" element={<VerificationDetailPage />} />
            <Route path="history" element={<PharmacistHistoryPage />} />
          </Route>
        </Route>

        <Route element={<RequireAuth roles={["admin"]} />}>
          <Route path="/admin" element={<StaffLayout area="admin" />}>
            <Route index element={<AdminDashboardPage />} />
            <Route path="medicines" element={<AdminMedicinesPage />} />
            <Route path="medicines/new" element={<AdminMedicineFormPage />} />
            <Route path="medicines/:id" element={<AdminMedicineFormPage />} />
            <Route path="categories" element={<AdminCategoriesPage />} />
            <Route path="users" element={<AdminUsersPage />} />
            <Route path="orders" element={<AdminOrdersPage />} />
            <Route path="orders/:id" element={<AdminOrderDetailPage />} />
            <Route path="prescriptions" element={<AdminPrescriptionsPage />} />
            <Route path="prescriptions/:id" element={<VerificationDetailPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}

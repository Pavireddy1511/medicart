import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Form";
import { useAuth } from "@/context/AuthContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { toApiError } from "@/services/http";

const initial = { full_name: "", mobile_number: "", email: "", password: "", confirm_password: "" };

export default function RegisterPage() {
  useDocumentTitle("Create account");
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const set = (key: keyof typeof initial) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const local: Record<string, string> = {};
    if (form.full_name.trim().length < 2) local.full_name = "Enter your full name";
    if (!/^\d{10}$/.test(form.mobile_number.replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "")))
      local.mobile_number = "Enter a valid 10-digit mobile number";
    if (form.password.length < 8) local.password = "Use at least 8 characters";
    else if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password))
      local.password = "Include at least one letter and one number";
    if (form.password !== form.confirm_password) local.confirm_password = "Passwords do not match";
    setFieldErrors(local);
    if (Object.keys(local).length) return;

    setLoading(true);
    try {
      await register({ ...form, email: form.email.trim() || undefined });
      navigate("/", { replace: true });
    } catch (err) {
      const apiError = toApiError(err);
      setFieldErrors(apiError.fieldErrors);
      if (apiError.code === "mobile_taken") setFieldErrors({ mobile_number: apiError.message });
      else if (apiError.code === "email_taken") setFieldErrors({ email: apiError.message });
      else if (!Object.keys(apiError.fieldErrors).length) setError(apiError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-2xl font-bold text-ink">Create your account</h1>
      <p className="mt-1 text-sm text-muted">Takes a minute. Only a mobile number and password are required.</p>

      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Input label="Full name" autoComplete="name" value={form.full_name} onChange={set("full_name")} error={fieldErrors.full_name} required />
        <Input
          label="Mobile number"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          placeholder="10-digit mobile number"
          value={form.mobile_number}
          onChange={set("mobile_number")}
          error={fieldErrors.mobile_number}
          required
        />
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          hint="Optional. Used for order updates."
          value={form.email}
          onChange={set("email")}
          error={fieldErrors.email}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters with a letter and a number."
          value={form.password}
          onChange={set("password")}
          error={fieldErrors.password}
          required
        />
        <Input
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          value={form.confirm_password}
          onChange={set("confirm_password")}
          error={fieldErrors.confirm_password}
          required
        />
        <Button type="submit" fullWidth size="lg" loading={loading}>
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-semibold text-brand-600 hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}

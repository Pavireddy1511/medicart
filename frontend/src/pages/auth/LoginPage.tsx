import { Eye, EyeOff, Phone } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Form";
import { homeFor, useAuth } from "@/context/AuthContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { toApiError } from "@/services/http";

export default function LoginPage() {
  useDocumentTitle("Sign in");
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    setLoading(true);
    try {
      const user = await login(mobile.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && user.role === "customer" ? from : homeFor(user.role), { replace: true });
    } catch (err) {
      const apiError = toApiError(err);
      setFieldErrors(apiError.fieldErrors);
      if (!Object.keys(apiError.fieldErrors).length) setError(apiError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-2xl font-bold text-ink">Sign in</h1>
      <p className="mt-1 text-sm text-muted">Use the mobile number you registered with.</p>

      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Input
          label="Mobile number"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          placeholder="10-digit mobile number"
          value={mobile}
          onChange={(e) => setMobile(e.target.value)}
          error={fieldErrors.mobile_number}
          leftIcon={<Phone className="h-4 w-4" />}
          required
        />
        <div className="relative">
          <Input
            label="Password"
            type={show ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
            required
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-3 top-[34px] text-muted hover:text-ink"
            aria-label={show ? "Hide password" : "Show password"}
          >
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        <Button type="submit" fullWidth size="lg" loading={loading}>
          Sign in
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        New to MediCart?{" "}
        <Link to="/register" className="font-semibold text-brand-600 hover:underline">
          Create an account
        </Link>
      </p>
    </>
  );
}

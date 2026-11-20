import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Form";
import { Card, PageHeader } from "@/components/ui/Layout";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { useDocumentTitle } from "@/hooks/useUtilities";
import { authApi } from "@/services/api";
import { toApiError } from "@/services/http";
import { formatDate } from "@/utils/format";

export default function ProfilePage() {
  useDocumentTitle("Profile");
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [profileErrors, setProfileErrors] = useState<Record<string, string>>({});
  const [savingProfile, setSavingProfile] = useState(false);

  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [passwordErrors, setPasswordErrors] = useState<Record<string, string>>({});
  const [savingPassword, setSavingPassword] = useState(false);

  if (!user) return null;

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setProfileErrors({});
    try {
      const updated = await authApi.updateProfile({ full_name: name.trim(), email: email.trim() || null });
      setUser(updated);
      toast.success("Profile updated");
    } catch (err) {
      const apiError = toApiError(err);
      setProfileErrors(apiError.fieldErrors);
      if (apiError.code === "email_taken") setProfileErrors({ email: apiError.message });
      else if (!Object.keys(apiError.fieldErrors).length) toast.error("Could not save", apiError.message);
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async (e: FormEvent) => {
    e.preventDefault();
    const local: Record<string, string> = {};
    if (passwords.new_password.length < 8 || !/[A-Za-z]/.test(passwords.new_password) || !/\d/.test(passwords.new_password))
      local.new_password = "At least 8 characters with a letter and a number";
    if (passwords.new_password !== passwords.confirm_password) local.confirm_password = "Passwords do not match";
    setPasswordErrors(local);
    if (Object.keys(local).length) return;
    setSavingPassword(true);
    try {
      await authApi.changePassword(passwords);
      setPasswords({ current_password: "", new_password: "", confirm_password: "" });
      toast.success("Password changed");
    } catch (err) {
      const apiError = toApiError(err);
      if (apiError.code === "invalid_credentials") setPasswordErrors({ current_password: apiError.message });
      else setPasswordErrors(apiError.fieldErrors);
      if (!Object.keys(apiError.fieldErrors).length && apiError.code !== "invalid_credentials") toast.error("Could not change password", apiError.message);
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Profile & security" description={`Member since ${formatDate(user.created_at)}`} actions={<Badge tone="brand" className="capitalize">{user.role}</Badge>} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="text-base font-semibold text-ink">Personal details</h2>
          <form onSubmit={saveProfile} className="mt-4 space-y-4" noValidate>
            <Input label="Full name" value={name} onChange={(e) => setName(e.target.value)} error={profileErrors.full_name} required />
            <Input label="Mobile number" value={`+91 ${user.mobile_number}`} disabled hint="Your mobile number is your login and cannot be changed here." />
            <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} error={profileErrors.email} hint="Optional" />
            <Button type="submit" loading={savingProfile}>Save changes</Button>
          </form>
        </Card>
        <Card>
          <h2 className="text-base font-semibold text-ink">Change password</h2>
          <form onSubmit={savePassword} className="mt-4 space-y-4" noValidate>
            <Input label="Current password" type="password" autoComplete="current-password" value={passwords.current_password} onChange={(e) => setPasswords((p) => ({ ...p, current_password: e.target.value }))} error={passwordErrors.current_password} required />
            <Input label="New password" type="password" autoComplete="new-password" value={passwords.new_password} onChange={(e) => setPasswords((p) => ({ ...p, new_password: e.target.value }))} error={passwordErrors.new_password} required />
            <Input label="Confirm new password" type="password" autoComplete="new-password" value={passwords.confirm_password} onChange={(e) => setPasswords((p) => ({ ...p, confirm_password: e.target.value }))} error={passwordErrors.confirm_password} required />
            <Button type="submit" variant="secondary" loading={savingPassword}>Update password</Button>
          </form>
        </Card>
      </div>
      <Card className="flex flex-wrap gap-4 text-sm">
        <Link to="/orders" className="font-semibold text-brand-600 hover:underline">My orders</Link>
        <Link to="/prescriptions" className="font-semibold text-brand-600 hover:underline">My prescriptions</Link>
        <Link to="/addresses" className="font-semibold text-brand-600 hover:underline">Saved addresses</Link>
      </Card>
    </div>
  );
}

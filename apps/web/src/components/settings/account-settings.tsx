"use client";

import { Loader2, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";
import type { User } from "@/types/api";

export function AccountSettings({ user }: { user: User }) {
  const router = useRouter();
  const [profile, setProfile] = React.useState({
    full_name: user.full_name,
    phone: user.phone ?? "",
  });
  const [passwords, setPasswords] = React.useState({ current_password: "", new_password: "" });
  const [savingProfile, setSavingProfile] = React.useState(false);
  const [savingPassword, setSavingPassword] = React.useState(false);

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      await api.patch("/auth/me", {
        full_name: profile.full_name,
        phone: profile.phone || null,
      });
      toast.success("Account updated");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not update account");
    } finally {
      setSavingProfile(false);
    }
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault();
    setSavingPassword(true);
    try {
      await api.post("/auth/change-password", passwords);
      // The API revokes every session on a password change — including this one.
      toast.success("Password updated — please sign in again");
      router.push("/login");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not change password");
      setSavingPassword(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveProfile} className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" htmlFor="full_name" required>
              <Input
                id="full_name"
                required
                minLength={2}
                value={profile.full_name}
                onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))}
              />
            </Field>
            <Field label="Phone number" htmlFor="phone">
              <Input
                id="phone"
                value={profile.phone}
                onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))}
              />
            </Field>
            <Field label="Email address" htmlFor="email" className="sm:col-span-2">
              <Input id="email" value={user.email} disabled />
            </Field>
            <div className="sm:col-span-2">
              <Button type="submit" variant="primary" disabled={savingProfile}>
                {savingProfile ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Save className="size-4" />
                )}
                Save changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={changePassword} className="grid gap-4 sm:grid-cols-2">
            <Field label="Current password" htmlFor="current_password" required>
              <PasswordInput
                id="current_password"
                required
                autoComplete="current-password"
                value={passwords.current_password}
                onChange={(e) =>
                  setPasswords((p) => ({ ...p, current_password: e.target.value }))
                }
              />
            </Field>
            <Field
              label="New password"
              htmlFor="new_password"
              required
              hint="Changing this signs out every device."
            >
              <PasswordInput
                id="new_password"
                required
                minLength={8}
                autoComplete="new-password"
                value={passwords.new_password}
                onChange={(e) => setPasswords((p) => ({ ...p, new_password: e.target.value }))}
              />
            </Field>
            <div className="sm:col-span-2">
              <Button type="submit" variant="outline" disabled={savingPassword}>
                {savingPassword ? <Loader2 className="size-4 animate-spin" /> : null}
                Change password
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

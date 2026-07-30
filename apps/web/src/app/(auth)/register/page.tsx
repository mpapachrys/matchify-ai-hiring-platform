"use client";

import { Briefcase, Loader2, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { Role, Session } from "@/types/api";

const ROLES: { value: Role; label: string; blurb: string; icon: typeof UserIcon }[] = [
  {
    value: "candidate",
    label: "Candidate",
    blurb: "Browse roles and track your applications",
    icon: UserIcon,
  },
  {
    value: "hiring_manager",
    label: "Hiring Manager",
    blurb: "Post roles and manage your pipeline",
    icon: Briefcase,
  },
];

export default function RegisterPage() {
  const router = useRouter();
  const [role, setRole] = React.useState<Role>("candidate");
  const [form, setForm] = React.useState({ full_name: "", email: "", password: "" });
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);

  function update(key: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [key]: event.target.value }));
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setPending(true);
    try {
      const session = await api.post<Session>("/auth/register", { ...form, role });
      router.push(
        session.user.role === "hiring_manager" ? "/manager/dashboard" : "/candidate/dashboard",
      );
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
      setPending(false);
    }
  }

  return (
    <Card>
      <CardContent className="p-6 pt-6">
        <h1 className="text-2xl font-bold text-foreground">Create your account</h1>
        <p className="mb-6 mt-1 text-sm text-muted">
          Your role decides which side of Matchify you land on.
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <fieldset>
            <legend className="mb-2 text-xs font-medium text-muted">I am a…</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {ROLES.map((option) => {
                const selected = role === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setRole(option.value)}
                    className={cn(
                      "rounded-xl border p-3 text-left transition-all",
                      selected
                        ? "border-primary bg-primary/15"
                        : "border-border bg-surface-2/40 hover:border-border-strong",
                    )}
                  >
                    <option.icon
                      className={cn("mb-2 size-5", selected ? "text-[#a78bfa]" : "text-subtle")}
                    />
                    <p className="text-sm font-semibold text-foreground">{option.label}</p>
                    <p className="mt-0.5 text-xs text-muted">{option.blurb}</p>
                  </button>
                );
              })}
            </div>
          </fieldset>

          <Field label="Full name" htmlFor="full_name" required>
            <Input
              id="full_name"
              required
              minLength={2}
              value={form.full_name}
              onChange={update("full_name")}
              placeholder="Nikos Koukis"
            />
          </Field>

          <Field label="Email address" htmlFor="email" required>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={update("email")}
              placeholder="you@example.com"
            />
          </Field>

          <Field
            label="Password"
            htmlFor="password"
            required
            hint="At least 8 characters."
          >
            <PasswordInput
              id="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={form.password}
              onChange={update("password")}
              placeholder="••••••••"
            />
          </Field>

          {error ? (
            <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          ) : null}

          <Button type="submit" variant="primary" className="w-full" disabled={pending}>
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            {pending ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          Already registered?{" "}
          <Link href="/login" className="font-semibold text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

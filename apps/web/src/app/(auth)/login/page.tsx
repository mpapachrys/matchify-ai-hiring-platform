"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";
import type { Session } from "@/types/api";

const DEMO_ACCOUNTS = [
  { label: "Hiring Manager", email: "manager@matchify.dev" },
  { label: "Candidate", email: "nikos@example.com" },
];

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);
  const expired = params.get("session") === "expired";

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const session = await api.post<Session>("/auth/login", { email, password });
      const fallback =
        session.user.role === "hiring_manager" ? "/manager/dashboard" : "/candidate/dashboard";
      router.push(params.get("next") ?? fallback);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
      setPending(false);
    }
  }

  return (
    <Card>
      <CardContent className="p-6 pt-6">
        <h1 className="text-2xl font-bold text-foreground">Welcome back</h1>
        <p className="mb-6 mt-1 text-sm text-muted">Sign in to continue to Matchify.</p>

        {expired ? (
          <p className="mb-4 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
            Your session ended. Please sign in again.
          </p>
        ) : null}

        <form onSubmit={onSubmit} className="space-y-4">
          <Field label="Email address" htmlFor="email" required>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </Field>

          <Field label="Password" htmlFor="password" required>
            <PasswordInput
              id="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="mt-6 rounded-lg border border-border bg-surface-2/50 p-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Demo accounts — password Passw0rd!
          </p>
          <div className="flex flex-wrap gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                onClick={() => {
                  setEmail(account.email);
                  setPassword("Passw0rd!");
                }}
                className="rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-primary/50 hover:text-foreground"
              >
                {account.label}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-6 text-center text-sm text-muted">
          No account?{" "}
          <Link href="/register" className="font-semibold text-accent hover:underline">
            Create one
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

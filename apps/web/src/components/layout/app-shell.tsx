"use client";

import { LogOut, Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { Avatar } from "@/components/ui/misc";
import { navFor } from "@/config/nav";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { User } from "@/types/api";

/**
 * The one shell both role layouts render.
 *
 * Route groups mean this is mounted exactly twice — once in (candidate), once
 * in (manager) — instead of being re-checked on every page.
 */
export function AppShell({
  user,
  orgName,
  children,
}: {
  user: User;
  orgName: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const items = navFor(user.role);

  const current = items.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );

  async function signOut() {
    await api.post("/auth/logout").catch(() => undefined);
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex min-h-screen">
      {/* backdrop for the mobile drawer */}
      {open ? (
        <button
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-[#0f0a1c]/95 backdrop-blur-xl transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border px-5">
          <Link href={`/${user.role === "hiring_manager" ? "manager" : "candidate"}/dashboard`} className="flex items-center gap-2">
            <Image src="/logo-mark.png" alt="Matchify" width={32} height={32} className="size-8" priority />
            <span className="text-base font-bold">
              <span className="text-foreground">Match</span>
              <span className="gradient-text">ify</span>
            </span>
          </Link>
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-subtle hover:text-foreground lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex items-center gap-3 border-b border-border px-5 py-4">
          <Avatar name={user.full_name} src={user.avatar_url} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{user.full_name}</p>
            <p className="truncate text-xs text-subtle">{user.email}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {items.map((item) => {
            const active = current?.href === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "border border-primary/40 bg-primary/15 text-foreground"
                    : "text-muted hover:bg-surface-2/70 hover:text-foreground",
                )}
              >
                <item.icon className="size-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border p-3">
          <button
            onClick={signOut}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-danger transition-colors hover:bg-danger/10"
          >
            <LogOut className="size-4" />
            Logout
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-[#0f0a1c]/80 px-4 backdrop-blur-xl sm:px-6">
          <button
            onClick={() => setOpen(true)}
            className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-foreground lg:hidden"
            aria-label="Open navigation"
          >
            <Menu className="size-5" />
          </button>
          <h2 className="text-sm font-semibold tracking-wide text-foreground">
            {current?.label ?? "Dashboard"}
          </h2>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-xs text-subtle sm:block">{orgName}</span>
            <Avatar name={user.full_name} src={user.avatar_url} className="size-8" />
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}

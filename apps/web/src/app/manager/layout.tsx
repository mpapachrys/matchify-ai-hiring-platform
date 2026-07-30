import { AppShell } from "@/components/layout/app-shell";
import { serverFetchOrNull } from "@/lib/api/server";
import { requireRole } from "@/lib/auth/session";
import type { Organization } from "@/types/api";

// Same reasoning as the candidate layout: never prerender per-user pages.
export const dynamic = "force-dynamic";

/** Manager role gate for the entire /manager subtree. */
export default async function ManagerLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("hiring_manager");
  const org = await serverFetchOrNull<Organization>("/organization");

  return (
    <AppShell user={user} orgName={org?.name ?? "Matchify"}>
      {children}
    </AppShell>
  );
}

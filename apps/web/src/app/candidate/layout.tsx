import { BookingWidget } from "@/components/agent/booking-widget";
import { AppShell } from "@/components/layout/app-shell";
import { serverFetchOrNull } from "@/lib/api/server";
import { requireRole } from "@/lib/auth/session";
import type { Organization } from "@/types/api";

// Every page under /candidate is per-user. Forcing dynamic rendering keeps the
// build from prerendering a signed-out shell (or one user's data) and serving
// it to everyone.
export const dynamic = "force-dynamic";

/**
 * The candidate role gate lives here — one check for the whole subtree, rather
 * than repeated on every page. `middleware.ts` also redirects, but only to
 * avoid a flash of the wrong shell; this is the server-side check.
 */
export default async function CandidateLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("candidate");
  const org = await serverFetchOrNull<Organization>("/organization");

  return (
    <AppShell user={user} orgName={org?.name ?? "Matchify"}>
      {children}
      <BookingWidget />
    </AppShell>
  );
}

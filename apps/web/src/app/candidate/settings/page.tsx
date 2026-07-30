import { AccountSettings } from "@/components/settings/account-settings";
import { PageHeader } from "@/components/ui/misc";
import { requireRole } from "@/lib/auth/session";

export const metadata = { title: "Settings" };

export default async function CandidateSettingsPage() {
  const user = await requireRole("candidate");
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Settings" description="Manage your account and password." />
      <AccountSettings user={user} />
    </div>
  );
}

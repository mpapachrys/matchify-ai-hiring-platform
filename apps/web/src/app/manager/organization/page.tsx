import { OrganizationForm } from "@/components/organization/organization-form";
import { PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { requireRole } from "@/lib/auth/session";
import type { Organization } from "@/types/api";

export const metadata = { title: "Organization" };

export default async function OrganizationPage() {
  const user = await requireRole("hiring_manager");
  const org = await serverFetch<Organization>("/organization");

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Organization"
        description="Company profile and hiring defaults. This deployment serves one company."
      />
      <OrganizationForm org={org} canEdit={user.is_admin} />
    </div>
  );
}

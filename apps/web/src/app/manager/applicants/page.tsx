import { ApplicantTable } from "@/components/applications/applicant-table";
import { StageFilter } from "@/components/applications/stage-filter";
import { PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import type { ManagerApplication, Page as PageType } from "@/types/api";

export const metadata = { title: "Applicants" };

type SearchParams = Promise<{ stage?: string }>;

export default async function AllApplicantsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const { stage } = await searchParams;
  const query = new URLSearchParams({ page_size: "100" });
  if (stage) query.set("stage", stage);

  // Org-wide feed — single-tenant means no company scoping to apply.
  const applications = await serverFetch<PageType<ManagerApplication>>(
    `/applications/manage?${query.toString()}`,
  );

  return (
    <div>
      <PageHeader
        title="All Applicants"
        description={`${applications.total} ${
          applications.total === 1 ? "application" : "applications"
        } across every job`}
      />
      <StageFilter />
      <ApplicantTable applications={applications.items} showJobColumn />
    </div>
  );
}

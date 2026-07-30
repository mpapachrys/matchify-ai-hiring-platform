import { ArrowLeft, KanbanSquare } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ApplicantTable } from "@/components/applications/applicant-table";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/misc";
import { ApiError, serverFetch } from "@/lib/api/server";
import type { ManagerApplication, ManagerJob, Page } from "@/types/api";

export const metadata = { title: "Applicants" };

export default async function JobApplicantsPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;

  let job: ManagerJob;
  try {
    job = await serverFetch<ManagerJob>(`/jobs/${jobId}/manage`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const applications = await serverFetch<Page<ManagerApplication>>(
    `/applications/job/${jobId}?page_size=100`,
  );

  return (
    <div>
      <Link
        href="/manager/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to jobs
      </Link>

      <PageHeader
        title={job.title}
        description={`${job.stats.applications} applicants · ${job.stats.shortlisted} shortlisted · ${job.stats.hired} hired`}
        action={
          <div className="flex items-center gap-2">
            <StatusBadge status={job.status} />
            <Button asChild variant="outline">
              <Link href={`/manager/jobs/${jobId}/pipeline`}>
                <KanbanSquare className="size-4" /> Pipeline view
              </Link>
            </Button>
          </div>
        }
      />

      <ApplicantTable applications={applications.items} />
    </div>
  );
}

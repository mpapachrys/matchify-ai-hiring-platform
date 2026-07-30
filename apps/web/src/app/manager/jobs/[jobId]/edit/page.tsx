import { notFound } from "next/navigation";

import { JobForm } from "@/components/jobs/job-form";
import { PageHeader } from "@/components/ui/misc";
import { ApiError, serverFetch } from "@/lib/api/server";
import type { ManagerJob } from "@/types/api";

export const metadata = { title: "Edit job" };

export default async function EditJobPage({
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

  if (!job.can_edit) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title={job.title} />
        <div className="panel p-6 text-sm text-muted">
          This job was created by another manager. You can review its applicants, but
          only its creator or an administrator can edit it.
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Edit Job" description={job.title} />
      <JobForm job={job} />
    </div>
  );
}

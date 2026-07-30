import { ArrowLeft, Table2 } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PipelineBoard } from "@/components/applications/pipeline-board";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/misc";
import { ApiError, serverFetch } from "@/lib/api/server";
import type { ManagerApplication, ManagerJob, Page } from "@/types/api";

export const metadata = { title: "Pipeline" };

export default async function JobPipelinePage({
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
    `/applications/job/${jobId}?page_size=200`,
  );

  return (
    <div>
      <Link
        href={`/manager/jobs/${jobId}/applicants`}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to applicants
      </Link>

      <PageHeader
        title={`${job.title} — Pipeline`}
        description="Drag a candidate between columns to change their stage."
        action={
          <Button asChild variant="outline">
            <Link href={`/manager/jobs/${jobId}/applicants`}>
              <Table2 className="size-4" /> Table view
            </Link>
          </Button>
        }
      />

      <PipelineBoard applications={applications.items} />
    </div>
  );
}

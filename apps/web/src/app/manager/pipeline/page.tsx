import { Briefcase } from "lucide-react";
import Link from "next/link";

import { PipelineBoard } from "@/components/applications/pipeline-board";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { cn } from "@/lib/utils";
import type { ManagerApplication, ManagerJob, Page as PageType } from "@/types/api";

export const metadata = { title: "Pipeline" };

type SearchParams = Promise<{ job?: string }>;

export default async function PipelinePage({ searchParams }: { searchParams: SearchParams }) {
  const { job: selectedJobId } = await searchParams;

  const jobs = await serverFetch<PageType<ManagerJob>>("/jobs/manage?page_size=100");
  const openJobs = jobs.items.filter((job) => job.status !== "archived");

  if (openJobs.length === 0) {
    return (
      <div>
        <PageHeader title="Pipeline" />
        <Card>
          <EmptyState
            icon={<Briefcase className="size-5" />}
            title="No jobs to track"
            description="Post a job first — the pipeline follows a job's applicants."
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/manager/jobs/new">Post a job</Link>
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  // Default to whichever posting has the most activity.
  const activeJob =
    openJobs.find((job) => job.id === selectedJobId) ??
    [...openJobs].sort((a, b) => b.stats.applications - a.stats.applications)[0];

  const applications = await serverFetch<PageType<ManagerApplication>>(
    `/applications/job/${activeJob.id}?page_size=200`,
  );

  return (
    <div>
      <PageHeader
        title="Pipeline"
        description="Drag a candidate between columns to change their stage."
      />

      <div className="mb-5 flex flex-wrap gap-1.5">
        {openJobs.map((job) => (
          <Link
            key={job.id}
            href={`/manager/pipeline?job=${job.id}`}
            className={cn(
              "flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors",
              job.id === activeJob.id
                ? "border-primary bg-primary/20 text-foreground"
                : "border-border bg-surface-2/40 text-muted hover:border-border-strong hover:text-foreground",
            )}
          >
            {job.title}
            <span className="rounded-full bg-surface px-1.5 text-[10px]">
              {job.stats.applications}
            </span>
          </Link>
        ))}
      </div>

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <p className="text-sm font-semibold text-foreground">{activeJob.title}</p>
            <p className="text-xs text-subtle">
              {activeJob.stats.applications} applicants · {activeJob.stats.shortlisted} shortlisted
              · {activeJob.stats.hired} hired
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={activeJob.status} />
            <Button asChild variant="outline" size="sm">
              <Link href={`/manager/jobs/${activeJob.id}/applicants`}>Table view</Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <PipelineBoard applications={applications.items} />
    </div>
  );
}

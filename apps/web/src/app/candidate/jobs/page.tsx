import { Search } from "lucide-react";
import { Suspense } from "react";

import { JobCard } from "@/components/jobs/job-card";
import { JobFilters } from "@/components/jobs/job-filters";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import type { Job, Page as PageType } from "@/types/api";

export const metadata = { title: "Browse Jobs" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

async function JobList({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = new URLSearchParams({ page_size: "24" });
  for (const key of ["search", "seniority", "work_mode", "category", "page"]) {
    const value = params[key];
    if (typeof value === "string" && value) query.set(key, value);
  }

  const jobs = await serverFetch<PageType<Job>>(`/jobs?${query.toString()}`);

  if (jobs.items.length === 0) {
    return (
      <div className="panel">
        <EmptyState
          icon={<Search className="size-5" />}
          title="No jobs match your filters"
          description="Try widening your search or clearing the filters."
        />
      </div>
    );
  }

  return (
    <>
      <p className="mb-4 text-sm text-muted">
        {jobs.total} open {jobs.total === 1 ? "role" : "roles"}
      </p>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {jobs.items.map((job) => (
          <JobCard key={job.id} job={job} href={`/candidate/jobs/${job.id}`} />
        ))}
      </div>
    </>
  );
}

export default function BrowseJobsPage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <div>
      <PageHeader
        title="Browse Jobs"
        description="Every role currently open. Apply once per role."
      />
      <Suspense fallback={null}>
        <JobFilters />
      </Suspense>
      <Suspense
        fallback={
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-48" />
            ))}
          </div>
        }
      >
        <JobList searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

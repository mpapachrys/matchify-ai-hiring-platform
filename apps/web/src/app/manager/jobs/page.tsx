import { Briefcase, Plus, Users } from "lucide-react";
import Link from "next/link";

import { JobRowActions } from "@/components/jobs/job-row-actions";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { formatDate, titleCase } from "@/lib/utils";
import type { ManagerJob, Page as PageType } from "@/types/api";

export const metadata = { title: "Jobs" };

export default async function ManagerJobsPage() {
  const jobs = await serverFetch<PageType<ManagerJob>>("/jobs/manage?page_size=100");

  return (
    <div>
      <PageHeader
        title="Jobs"
        description={`${jobs.total} ${jobs.total === 1 ? "posting" : "postings"} across the organization`}
        action={
          <Button asChild variant="primary">
            <Link href="/manager/jobs/new">
              <Plus className="size-4" /> Post a job
            </Link>
          </Button>
        }
      />

      {jobs.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Briefcase className="size-5" />}
            title="No jobs yet"
            description="Create your first posting to start collecting applications."
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/manager/jobs/new">Post a job</Link>
              </Button>
            }
          />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {/* Wide table scrolls inside its own container, not the page body. */}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-subtle">
                    <th className="px-5 py-3 font-semibold">Role</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Applicants</th>
                    <th className="px-5 py-3 font-semibold">Shortlisted</th>
                    <th className="px-5 py-3 font-semibold">Posted</th>
                    <th className="px-5 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {jobs.items.map((job) => (
                    <tr key={job.id} className="transition-colors hover:bg-surface-2/40">
                      <td className="px-5 py-3.5">
                        <Link
                          href={`/manager/jobs/${job.id}/applicants`}
                          className="font-semibold text-foreground hover:text-[#c4b5fd]"
                        >
                          {job.title}
                        </Link>
                        <p className="text-xs text-subtle">
                          {titleCase(job.seniority)} · {titleCase(job.work_mode)}
                        </p>
                      </td>
                      <td className="px-5 py-3.5">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="flex items-center gap-1.5 text-foreground">
                          <Users className="size-3.5 text-subtle" />
                          {job.stats.applications}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-foreground">{job.stats.shortlisted}</td>
                      <td className="px-5 py-3.5 text-muted">
                        {job.published_at ? formatDate(job.published_at) : "—"}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <JobRowActions job={job} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

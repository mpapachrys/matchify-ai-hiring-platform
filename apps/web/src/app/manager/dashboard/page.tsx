import { Award, Briefcase, Plus, Star, Users } from "lucide-react";
import Link from "next/link";

import { ApplicationsOverTime, HiringFunnel } from "@/components/charts/charts";
import { StatTile } from "@/components/charts/stat-tile";
import { StageBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, EmptyState } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { relativeTime } from "@/lib/utils";
import { requireRole } from "@/lib/auth/session";
import type { ManagerAnalytics, ManagerApplication, Page } from "@/types/api";

export const metadata = { title: "Dashboard" };

export default async function ManagerDashboard() {
  const user = await requireRole("hiring_manager");

  const [analytics, recent] = await Promise.all([
    serverFetch<ManagerAnalytics>("/analytics/manager"),
    serverFetch<Page<ManagerApplication>>("/applications/manage?page_size=6"),
  ]);

  return (
    <div className="space-y-6">
      <section className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-primary/25 via-primary/10 to-transparent p-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Welcome back, {user.full_name.split(" ")[0]}! 👋
            </h1>
            <p className="mt-1 text-sm text-muted">Here&rsquo;s how hiring is tracking.</p>
          </div>
          <Button asChild variant="primary">
            <Link href="/manager/jobs/new">
              <Plus className="size-4" /> Post a job
            </Link>
          </Button>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          icon={<Briefcase className="size-5" />}
          value={analytics.open_jobs}
          label="Open Jobs"
          tone="accent"
        />
        <StatTile
          icon={<Users className="size-5" />}
          value={analytics.total_applications}
          label="Applications"
          tone="primary"
        />
        <StatTile
          icon={<Star className="size-5" />}
          value={analytics.shortlisted}
          label="Shortlisted"
          tone="warning"
        />
        <StatTile
          icon={<Award className="size-5" />}
          value={analytics.hired}
          label="Hired"
          tone="success"
          hint={`${analytics.conversion_rate}% conversion`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ApplicationsOverTime data={analytics.applications_over_time} />
        <HiringFunnel data={analytics.funnel} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent Applicants</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/manager/applicants">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {recent.items.length === 0 ? (
              <EmptyState
                icon={<Users className="size-5" />}
                title="No applicants yet"
                description="Publish a job to start receiving applications."
              />
            ) : (
              <ul className="divide-y divide-border/60">
                {recent.items.map((application) => (
                  <li key={application.id} className="flex items-center gap-3 px-5 py-3">
                    <Avatar
                      name={application.candidate_snapshot.full_name}
                      src={application.candidate_snapshot.avatar_url}
                      className="size-8"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {application.candidate_snapshot.full_name}
                      </p>
                      <p className="truncate text-xs text-subtle">
                        {application.job_snapshot.title} · {relativeTime(application.applied_at)}
                      </p>
                    </div>
                    <StageBadge stage={application.stage} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Top Jobs by Volume</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/manager/jobs">Manage jobs</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {analytics.top_jobs.length === 0 ? (
              <EmptyState
                icon={<Briefcase className="size-5" />}
                title="No jobs posted"
                action={
                  <Button asChild variant="primary" size="sm">
                    <Link href="/manager/jobs/new">Post a job</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="divide-y divide-border/60">
                {analytics.top_jobs.map((job) => (
                  <li key={job.id} className="flex items-center gap-3 px-5 py-3">
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/manager/jobs/${job.id}/applicants`}
                        className="truncate text-sm font-semibold text-foreground hover:text-[#c4b5fd]"
                      >
                        {job.title}
                      </Link>
                      <p className="text-xs text-subtle">
                        {job.applications} applicants · {job.shortlisted} shortlisted
                      </p>
                    </div>
                    <StatusBadge status={job.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

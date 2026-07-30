import { Award, CheckCircle2, FileText, Globe, TrendingUp } from "lucide-react";
import Link from "next/link";

import { ApplicationsOverTime, SuccessRateTrend } from "@/components/charts/charts";
import { StatTile } from "@/components/charts/stat-tile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StageBadge } from "@/components/ui/badge";
import { EmptyState, Progress } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { requireRole } from "@/lib/auth/session";
import { relativeTime } from "@/lib/utils";
import type { CandidateAnalytics, CandidateApplication, Page } from "@/types/api";

export const metadata = { title: "Dashboard" };

export default async function CandidateDashboard() {
  const user = await requireRole("candidate");

  // Independent reads — fire them together rather than waterfalling.
  const [analytics, applications] = await Promise.all([
    serverFetch<CandidateAnalytics>("/analytics/candidate"),
    serverFetch<Page<CandidateApplication>>("/applications/me?page_size=5"),
  ]);

  return (
    <div className="space-y-6">
      <section className="panel overflow-hidden">
        <div className="bg-gradient-to-r from-primary/25 via-primary/10 to-transparent p-6">
          <h1 className="text-2xl font-bold text-foreground">
            Welcome back, {user.full_name.split(" ")[0]}! 👋
          </h1>
          <p className="mt-1 text-sm text-muted">Here&rsquo;s your job application overview.</p>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          icon={<Globe className="size-5" />}
          value={analytics.jobs_applied}
          label="Jobs Applied"
          tone="accent"
        />
        <StatTile
          icon={<CheckCircle2 className="size-5" />}
          value={analytics.shortlisted}
          label="Shortlisted"
          tone="success"
        />
        <StatTile
          icon={<FileText className="size-5" />}
          value={analytics.in_interview}
          label="In Interview"
          tone="primary"
        />
        <StatTile
          icon={<Award className="size-5" />}
          value={analytics.offers}
          label="Offers"
          tone="warning"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ApplicationsOverTime data={analytics.applications_over_time} />
        <SuccessRateTrend data={analytics.success_rate_trend} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent Applications</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/candidate/applications">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {applications.items.length === 0 ? (
              <EmptyState
                icon={<FileText className="size-5" />}
                title="No applications yet"
                description="Browse open roles and submit your first application."
                action={
                  <Button asChild variant="primary" size="sm">
                    <Link href="/candidate/jobs">Browse jobs</Link>
                  </Button>
                }
              />
            ) : (
              <ul className="divide-y divide-border/60">
                {applications.items.map((application) => (
                  <li key={application.id} className="flex items-center gap-3 px-5 py-3.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {application.job_snapshot.title}
                      </p>
                      <p className="text-xs text-subtle">
                        {application.job_snapshot.location ?? "—"} ·{" "}
                        {relativeTime(application.applied_at)}
                      </p>
                    </div>
                    <StageBadge stage={application.stage} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-muted">Success rate</span>
                  <span className="flex items-center gap-1 text-2xl font-bold text-success">
                    {analytics.success_rate}%
                    <TrendingUp className="size-4" />
                  </span>
                </div>
                <p className="mt-1 text-xs text-subtle">
                  {analytics.shortlisted} shortlisted out of {analytics.jobs_applied} applications
                </p>
              </div>
              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <span className="text-xs text-muted">Profile completion</span>
                  <span className="text-sm font-semibold text-foreground">
                    {analytics.profile_completion}%
                  </span>
                </div>
                <Progress value={analytics.profile_completion} />
                {analytics.profile_completion < 100 ? (
                  <Button asChild variant="outline" size="sm" className="mt-3 w-full">
                    <Link href="/candidate/resume-builder">Complete your profile</Link>
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

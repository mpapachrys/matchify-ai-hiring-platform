import { FileText } from "lucide-react";
import Link from "next/link";

import { CandidateMatchBadge } from "@/components/applications/match-badge";
import { WithdrawButton } from "@/components/applications/withdraw-button";
import { StageBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { formatDate, titleCase } from "@/lib/utils";
import type { CandidateApplication, Page as PageType } from "@/types/api";

export const metadata = { title: "My Applications" };

const ACTIVE_STAGES = ["applied", "screening", "interview", "offer"];

export default async function MyApplicationsPage() {
  const applications = await serverFetch<PageType<CandidateApplication>>(
    "/applications/me?page_size=100",
  );

  if (applications.items.length === 0) {
    return (
      <div>
        <PageHeader title="My Applications" />
        <Card>
          <EmptyState
            icon={<FileText className="size-5" />}
            title="No applications yet"
            description="Once you apply to a role it will show up here with its current stage."
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/candidate/jobs">Browse jobs</Link>
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="My Applications"
        description={`${applications.total} total · ${
          applications.items.filter((a) => ACTIVE_STAGES.includes(a.stage)).length
        } still active`}
      />

      <div className="space-y-3">
        {applications.items.map((application) => {
          const isActive = ACTIVE_STAGES.includes(application.stage);
          return (
            <Card key={application.id}>
              <CardContent className="flex flex-wrap items-center gap-4 p-5">
                <div className="min-w-56 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold text-foreground">
                      {application.job_snapshot.title}
                    </h2>
                    <StageBadge stage={application.stage} />
                    <CandidateMatchBadge
                      status={application.match_status}
                      confidence={application.match_confidence}
                    />
                  </div>
                  <p className="mt-1 text-xs text-subtle">
                    {application.job_snapshot.location ?? "—"} ·{" "}
                    {titleCase(application.job_snapshot.employment_type ?? "")} · Applied{" "}
                    {formatDate(application.applied_at)}
                  </p>

                  {application.timeline.length > 1 ? (
                    <ol className="mt-3 flex flex-wrap items-center gap-2">
                      {application.timeline.map((entry, index) => (
                        <li key={index} className="flex items-center gap-2">
                          {index > 0 ? <span className="text-subtle">→</span> : null}
                          <span className="text-[11px] text-muted">
                            {titleCase(entry.to_stage)}
                            <span className="ml-1 text-subtle">
                              {formatDate(entry.changed_at)}
                            </span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </div>

                <div className="flex items-center gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/candidate/jobs/${application.job_id}`}>View job</Link>
                  </Button>
                  {isActive ? <WithdrawButton applicationId={application.id} /> : null}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

import { Calendar as CalendarIcon } from "lucide-react";

import { BookInterviewDialog } from "@/components/calendar/book-interview-dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { formatInterviewSlot } from "@/lib/utils";
import type { CandidateApplication, Page as PageType } from "@/types/api";

export const metadata = { title: "Interviews" };

export default async function CandidateInterviewsPage() {
  const applications = await serverFetch<PageType<CandidateApplication>>(
    "/applications/me?page_size=100",
  );
  const relevant = applications.items.filter(
    (a) => a.interview.status === "awaiting_candidate" || a.interview.status === "scheduled",
  );

  return (
    <div>
      <PageHeader
        title="Interviews"
        description="Once a hiring manager approves you, pick a time here. They don't choose it for you."
      />

      {relevant.length === 0 ? (
        <Card>
          <EmptyState
            icon={<CalendarIcon className="size-5" />}
            title="No interviews yet"
            description="Once a hiring manager approves you for an interview, it will show up here for you to pick a time."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {relevant.map((application) => {
            const awaitingSlot = application.interview.status === "awaiting_candidate";
            return (
              <Card key={application.id}>
                <CardContent className="flex flex-wrap items-center gap-4 p-5">
                  <div className="min-w-56 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-foreground">
                        {application.job_snapshot.title}
                      </p>
                      {awaitingSlot ? <Badge tone="warning">Pick a time</Badge> : null}
                    </div>
                    {!awaitingSlot &&
                    application.interview.scheduled_start &&
                    application.interview.scheduled_end ? (
                      <p className="mt-1 text-xs font-medium text-muted">
                        {formatInterviewSlot(
                          application.interview.scheduled_start,
                          application.interview.scheduled_end,
                          { weekday: "long" },
                        )}
                      </p>
                    ) : null}
                  </div>
                  {awaitingSlot ? (
                    <BookInterviewDialog
                      applicationId={application.id}
                      jobTitle={application.job_snapshot.title}
                    />
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

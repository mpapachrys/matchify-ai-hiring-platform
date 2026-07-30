import { Calendar as CalendarIcon } from "lucide-react";

import { CancelInterviewButton } from "@/components/calendar/cancel-interview-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, EmptyState, PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import { formatInterviewSlot } from "@/lib/utils";
import type { ManagerApplication, Page as PageType } from "@/types/api";

export const metadata = { title: "Calendar" };

export default async function ManagerCalendarPage() {
  const interviews = await serverFetch<PageType<ManagerApplication>>(
    "/applications/interviews?page_size=100",
  );

  return (
    <div>
      <PageHeader
        title="Calendar"
        description="Approve an applicant for interview from their row — the candidate then picks the actual slot here."
      />

      {interviews.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<CalendarIcon className="size-5" />}
            title="No interviews approved or scheduled"
            description="Use the approve icon on an applicant's row to invite them to pick a slot."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {interviews.items.map((application) => {
            const isBooked = application.interview.status === "scheduled";
            return (
              <Card key={application.id}>
                <CardContent className="flex flex-wrap items-center gap-4 p-5">
                  <Avatar
                    name={application.candidate_snapshot.full_name}
                    src={application.candidate_snapshot.avatar_url}
                  />
                  <div className="min-w-56 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-foreground">
                        {application.candidate_snapshot.full_name}
                      </p>
                      {isBooked ? null : (
                        <Badge tone="warning">Waiting on candidate</Badge>
                      )}
                    </div>
                    <p className="text-xs text-subtle">{application.job_snapshot.title}</p>
                    {isBooked &&
                    application.interview.scheduled_start &&
                    application.interview.scheduled_end ? (
                      <p className="mt-1 text-xs font-medium text-muted">
                        {formatInterviewSlot(
                          application.interview.scheduled_start,
                          application.interview.scheduled_end,
                        )}
                      </p>
                    ) : null}
                  </div>
                  <CancelInterviewButton
                    applicationId={application.id}
                    variant={isBooked ? "scheduled" : "awaiting_candidate"}
                  />
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

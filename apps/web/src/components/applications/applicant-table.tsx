"use client";

import { CalendarCheck2, CalendarClock, CalendarX, FileText, Loader2, MessageSquare, Star, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ManagerMatchBadge } from "@/components/applications/match-badge";
import { ApproveInterviewButton } from "@/components/calendar/approve-interview-button";
import { CancelInterviewButton } from "@/components/calendar/cancel-interview-button";
import { StageBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Select, Textarea } from "@/components/ui/field";
import { Avatar, EmptyState } from "@/components/ui/misc";
import { ApiError, api } from "@/lib/api/client";
import { formatDate, relativeTime } from "@/lib/utils";
import type { ManagerApplication, PipelineStage } from "@/types/api";

/** Managers move candidates here; `withdrawn` is candidate-only and never offered. */
const ASSIGNABLE_STAGES: PipelineStage[] = [
  "applied",
  "screening",
  "interview",
  "offer",
  "hired",
  "rejected",
];

export function ApplicantTable({
  applications,
  showJobColumn = false,
}: {
  applications: ManagerApplication[];
  showJobColumn?: boolean;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [noteTarget, setNoteTarget] = React.useState<ManagerApplication | null>(null);
  const [noteBody, setNoteBody] = React.useState("");

  async function act(id: string, fn: () => Promise<unknown>, message: string) {
    setBusyId(id);
    try {
      await fn();
      toast.success(message);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  if (applications.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={<Users className="size-5" />}
          title="No applicants yet"
          description="Applications will appear here as soon as candidates apply."
        />
      </Card>
    );
  }

  return (
    <>
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-subtle">
                  <th className="px-5 py-3 font-semibold">Candidate</th>
                  {showJobColumn ? <th className="px-5 py-3 font-semibold">Role</th> : null}
                  <th className="px-5 py-3 font-semibold">Applied</th>
                  <th className="px-5 py-3 font-semibold">Match</th>
                  <th className="px-5 py-3 font-semibold">Stage</th>
                  <th className="px-5 py-3 font-semibold">Move to</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {applications.map((application) => {
                  const busy = busyId === application.id;
                  const closed =
                    application.stage === "withdrawn" || application.stage === "rejected";
                  return (
                    <tr key={application.id} className="transition-colors hover:bg-surface-2/40">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar
                            name={application.candidate_snapshot.full_name}
                            src={application.candidate_snapshot.avatar_url}
                            className="size-8"
                          />
                          <div className="min-w-0">
                            <Link
                              href={`/manager/candidates/${application.candidate_id}`}
                              className="block truncate font-semibold text-foreground hover:text-[#c4b5fd]"
                            >
                              {application.candidate_snapshot.full_name}
                            </Link>
                            <p className="truncate text-xs text-subtle">
                              {application.candidate_snapshot.headline ??
                                application.candidate_snapshot.email}
                            </p>
                          </div>
                          {application.is_shortlisted ? (
                            <Star className="size-3.5 shrink-0 fill-warning text-warning" />
                          ) : null}
                        </div>
                      </td>

                      {showJobColumn ? (
                        <td className="px-5 py-3 text-muted">{application.job_snapshot.title}</td>
                      ) : null}

                      <td className="px-5 py-3 text-muted" title={formatDate(application.applied_at)}>
                        {relativeTime(application.applied_at)}
                      </td>

                      <td className="px-5 py-3">
                        <ManagerMatchBadge match={application.match} />
                      </td>

                      <td className="px-5 py-3">
                        <StageBadge stage={application.stage} />
                      </td>

                      <td className="px-5 py-3">
                        <Select
                          aria-label={`Move ${application.candidate_snapshot.full_name} to another stage`}
                          className="w-36"
                          value={application.stage}
                          disabled={busy || application.stage === "withdrawn"}
                          onChange={(event) => {
                            const target = event.target.value as PipelineStage;
                            if (target === application.stage) return;
                            void act(
                              application.id,
                              () =>
                                api.patch(`/applications/${application.id}/stage`, {
                                  stage: target,
                                }),
                              `Moved to ${target}`,
                            );
                          }}
                        >
                          {/* A withdrawn application has no assignable stage to show as
                              selected — the select is disabled, so this is display only. */}
                          {application.stage === "withdrawn" ? (
                            <option value="withdrawn">Withdrawn</option>
                          ) : null}
                          {ASSIGNABLE_STAGES.map((stage) => (
                            <option key={stage} value={stage}>
                              {stage.charAt(0).toUpperCase() + stage.slice(1)}
                            </option>
                          ))}
                        </Select>
                      </td>

                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {busy ? (
                            <Loader2 className="size-4 animate-spin text-subtle" />
                          ) : (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                title={
                                  application.is_shortlisted ? "Remove shortlist" : "Shortlist"
                                }
                                disabled={closed}
                                onClick={() =>
                                  act(
                                    application.id,
                                    () =>
                                      api.patch(`/applications/${application.id}/shortlist`, {
                                        is_shortlisted: !application.is_shortlisted,
                                      }),
                                    application.is_shortlisted
                                      ? "Removed from shortlist"
                                      : "Added to shortlist",
                                  )
                                }
                              >
                                <Star
                                  className={
                                    application.is_shortlisted
                                      ? "size-4 fill-warning text-warning"
                                      : "size-4"
                                  }
                                />
                              </Button>

                              <Button
                                variant="ghost"
                                size="icon"
                                title={`Notes (${application.notes.length})`}
                                onClick={() => {
                                  setNoteTarget(application);
                                  setNoteBody("");
                                }}
                              >
                                <MessageSquare className="size-4" />
                                {application.notes.length > 0 ? (
                                  <span className="sr-only">
                                    {application.notes.length} notes
                                  </span>
                                ) : null}
                              </Button>

                              {application.interview.status === "scheduled" ? (
                                <CancelInterviewButton
                                  applicationId={application.id}
                                  variant="scheduled"
                                  trigger={
                                    <Button variant="ghost" size="icon" title="Cancel interview">
                                      <CalendarX className="size-4 text-danger" />
                                    </Button>
                                  }
                                />
                              ) : application.interview.status === "awaiting_candidate" ? (
                                <CancelInterviewButton
                                  applicationId={application.id}
                                  variant="awaiting_candidate"
                                  trigger={
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      title="Approved — waiting on the candidate to pick a slot"
                                    >
                                      <CalendarClock className="size-4 text-warning" />
                                    </Button>
                                  }
                                />
                              ) : (
                                <ApproveInterviewButton
                                  applicationId={application.id}
                                  candidateName={application.candidate_snapshot.full_name}
                                  trigger={
                                    <Button variant="ghost" size="icon" title="Approve for interview">
                                      <CalendarCheck2 className="size-4" />
                                    </Button>
                                  }
                                />
                              )}

                              {application.resume_id ? (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  title="Open resume"
                                  onClick={async () => {
                                    try {
                                      const { url } = await api.get<{ url: string }>(
                                        `/documents/${application.resume_id}/url`,
                                      );
                                      window.open(url, "_blank", "noopener");
                                    } catch {
                                      toast.error("Could not open resume");
                                    }
                                  }}
                                >
                                  <FileText className="size-4" />
                                </Button>
                              ) : null}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={Boolean(noteTarget)} onOpenChange={(open) => !open && setNoteTarget(null)}>
        {noteTarget ? (
          <DialogContent
            title={`Notes — ${noteTarget.candidate_snapshot.full_name}`}
            description="Internal only. Candidates never see these."
          >
            <div className="space-y-3">
              {noteTarget.notes.length === 0 ? (
                <p className="text-sm text-subtle">No notes yet.</p>
              ) : (
                <ul className="max-h-56 space-y-2 overflow-y-auto">
                  {noteTarget.notes.map((note, index) => (
                    <li key={index} className="rounded-lg border border-border bg-surface-2/50 p-3">
                      <p className="text-sm text-foreground">{note.body}</p>
                      <p className="mt-1 text-xs text-subtle">
                        {note.author_name} · {formatDate(note.created_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}

              {noteTarget.cover_letter ? (
                <details className="rounded-lg border border-border bg-surface-2/30 p-3">
                  <summary className="cursor-pointer text-xs font-semibold text-muted">
                    Cover letter
                  </summary>
                  <p className="mt-2 whitespace-pre-line text-sm text-muted">
                    {noteTarget.cover_letter}
                  </p>
                </details>
              ) : null}

              <Textarea
                rows={3}
                value={noteBody}
                onChange={(event) => setNoteBody(event.target.value)}
                placeholder="Add a note about this candidate…"
                aria-label="New note"
              />

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setNoteTarget(null)}>
                  Close
                </Button>
                <Button
                  variant="primary"
                  disabled={!noteBody.trim()}
                  onClick={async () => {
                    const target = noteTarget;
                    setNoteTarget(null);
                    await act(
                      target.id,
                      () => api.post(`/applications/${target.id}/notes`, { body: noteBody.trim() }),
                      "Note added",
                    );
                  }}
                >
                  Add note
                </Button>
              </div>
            </div>
          </DialogContent>
        ) : null}
      </Dialog>
    </>
  );
}

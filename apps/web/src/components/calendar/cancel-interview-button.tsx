"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api/client";

const COPY = {
  // Booked on the calendar already — a real event gets deleted.
  scheduled: {
    label: "Cancel interview",
    title: "Cancel this interview?",
    description: "Removes the event from the shared calendar. The candidate is not automatically notified.",
    success: "Interview cancelled",
  },
  // Approved but the candidate hasn't picked a slot yet — nothing on the
  // calendar to remove, this just revokes the approval.
  awaiting_candidate: {
    label: "Revoke approval",
    title: "Revoke this interview approval?",
    description: "The candidate will no longer be able to pick a slot until you approve them again.",
    success: "Interview approval revoked",
  },
} as const;

export function CancelInterviewButton({
  applicationId,
  variant = "scheduled",
  trigger,
}: {
  applicationId: string;
  variant?: keyof typeof COPY;
  /** Defaults to a labeled danger button; pass an icon button for tight
   * layouts like the applicant table. */
  trigger?: React.ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [pending, setPending] = React.useState(false);
  const copy = COPY[variant];

  async function cancel() {
    setPending(true);
    try {
      await api.del(`/applications/${applicationId}/interview`);
      toast.success(copy.success);
      setOpen(false);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not cancel the interview");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="danger" size="sm">
            {copy.label}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent title={copy.title} description={copy.description}>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Keep it
          </Button>
          <Button variant="danger" onClick={cancel} disabled={pending}>
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            {copy.label}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

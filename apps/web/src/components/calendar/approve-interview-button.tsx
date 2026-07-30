"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api/client";

export function ApproveInterviewButton({
  applicationId,
  candidateName,
  trigger,
}: {
  applicationId: string;
  candidateName: string;
  /** Defaults to a labeled button; pass an icon button for tight layouts
   * like the applicant table. */
  trigger?: React.ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [pending, setPending] = React.useState(false);

  async function approve() {
    setPending(true);
    try {
      await api.post(`/applications/${applicationId}/interview/approve`);
      toast.success("Interview approved — the candidate can now pick a slot");
      setOpen(false);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not approve the interview");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm">
            Approve for interview
          </Button>
        )}
      </DialogTrigger>
      <DialogContent
        title={`Approve ${candidateName} for an interview?`}
        description="This moves them to the Interview stage and lets them pick a slot on the shared calendar — you don't choose the time yourself."
      >
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={approve} disabled={pending}>
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            Approve
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

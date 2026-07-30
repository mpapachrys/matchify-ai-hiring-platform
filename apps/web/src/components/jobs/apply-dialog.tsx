"use client";

import { CheckCircle2, Loader2, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";

export function ApplyDialog({
  jobId,
  jobTitle,
  hasApplied,
  hasResume,
}: {
  jobId: string;
  jobTitle: string;
  hasApplied: boolean;
  hasResume: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [coverLetter, setCoverLetter] = React.useState("");
  const [pending, setPending] = React.useState(false);

  if (hasApplied) {
    return (
      <Button variant="outline" disabled className="w-full sm:w-auto">
        <CheckCircle2 className="size-4" /> Already applied
      </Button>
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    try {
      await api.post("/applications", {
        job_id: jobId,
        cover_letter: coverLetter.trim() || null,
      });
      toast.success("Application submitted", {
        description: `You applied to ${jobTitle}.`,
      });
      setOpen(false);
      router.refresh();
    } catch (error) {
      // 409 is the unique index doing its job — surface it as a normal message.
      toast.error(error instanceof ApiError ? error.message : "Could not submit application");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary" size="lg" className="w-full sm:w-auto">
          <Send className="size-4" /> Apply now
        </Button>
      </DialogTrigger>
      <DialogContent
        title={`Apply to ${jobTitle}`}
        description="Your profile and primary resume are attached automatically."
      >
        <form onSubmit={submit} className="space-y-4">
          {!hasResume ? (
            <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
              No resume uploaded yet — you can still apply, but adding one from the
              Documents page makes a stronger application.
            </p>
          ) : null}

          <Field
            label="Cover letter"
            htmlFor="cover_letter"
            hint="Optional. A few sentences on why this role fits."
          >
            <Textarea
              id="cover_letter"
              rows={6}
              maxLength={8000}
              value={coverLetter}
              onChange={(event) => setCoverLetter(event.target.value)}
              placeholder="I'm interested in this role because…"
            />
          </Field>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={pending}>
              {pending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              Submit application
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

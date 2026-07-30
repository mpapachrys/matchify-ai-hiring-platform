"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api/client";

export function WithdrawButton({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [pending, setPending] = React.useState(false);

  async function withdraw() {
    setPending(true);
    try {
      await api.post(`/applications/${applicationId}/withdraw`);
      toast.success("Application withdrawn");
      setOpen(false);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not withdraw");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="danger" size="sm">
          Withdraw
        </Button>
      </DialogTrigger>
      <DialogContent
        title="Withdraw this application?"
        description="This cannot be undone — one application per job means you will not be able to re-apply."
      >
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Keep it
          </Button>
          <Button variant="danger" onClick={withdraw} disabled={pending}>
            {pending ? <Loader2 className="size-4 animate-spin" /> : null}
            Withdraw application
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

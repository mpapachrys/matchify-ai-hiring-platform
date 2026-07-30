"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { SlotPicker } from "@/components/calendar/slot-picker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { AvailabilityOut, InterviewActionOut } from "@/types/api";

/** Next N weekdays as "YYYY-MM-DD" — interviews are Mon–Fri only, so weekends
 * are never offered in the first place rather than shown and disabled. */
function nextWeekdays(count: number): string[] {
  const days: string[] = [];
  const cursor = new Date();
  cursor.setDate(cursor.getDate() + 1);
  while (days.length < count) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) {
      days.push(cursor.toISOString().slice(0, 10));
    }
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

function formatDayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Candidate-facing: books their own approved interview onto the shared
 * calendar. The manager never picks the time — see approve-interview-button. */
export function BookInterviewDialog({
  applicationId,
  jobTitle,
  trigger,
}: {
  applicationId: string;
  jobTitle: string;
  trigger?: React.ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [days] = React.useState(() => nextWeekdays(10));
  const [selectedDate, setSelectedDate] = React.useState(days[0]);
  const [availability, setAvailability] = React.useState<AvailabilityOut | null>(null);
  const [loadingSlots, setLoadingSlots] = React.useState(false);
  const [selectedSlot, setSelectedSlot] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState(false);

  const loadAvailability = React.useCallback(async (date: string) => {
    setLoadingSlots(true);
    setSelectedSlot(null);
    try {
      setAvailability(await api.get<AvailabilityOut>(`/calendar/availability?date=${date}`));
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not load availability");
      setAvailability(null);
    } finally {
      setLoadingSlots(false);
    }
  }, []);

  React.useEffect(() => {
    if (open) void loadAvailability(selectedDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function selectDate(date: string) {
    setSelectedDate(date);
    void loadAvailability(date);
  }

  async function confirm() {
    if (!selectedSlot) return;
    setPending(true);
    try {
      const result = await api.post<InterviewActionOut>(
        `/applications/${applicationId}/interview/book`,
        { date: selectedDate, slot: selectedSlot },
      );
      if (result.status === "scheduled") {
        toast.success(result.message);
        setOpen(false);
        router.refresh();
      } else {
        // "conflict" / "invalid_request" — re-checked at booking time, the
        // picker's cached state is now stale.
        toast.error(result.message);
        void loadAvailability(selectedDate);
      }
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not book the interview");
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? <Button size="sm">Pick a time</Button>}
      </DialogTrigger>
      <DialogContent title="Pick an interview time" description={jobTitle} locked={pending}>
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">Day</p>
            <div className="flex flex-wrap gap-1.5">
              {days.map((date) => (
                <button
                  key={date}
                  type="button"
                  disabled={pending}
                  onClick={() => selectDate(date)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                    date === selectedDate
                      ? "border-primary bg-primary/20 text-foreground"
                      : "border-border bg-surface-2/40 text-muted hover:border-border-strong hover:text-foreground",
                  )}
                >
                  {formatDayLabel(date)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">
              Time slot
            </p>
            <SlotPicker
              slots={availability?.slots ?? null}
              loading={loadingSlots}
              selected={selectedSlot}
              onSelect={setSelectedSlot}
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={pending}>
              Cancel
            </Button>
            <Button variant="primary" onClick={confirm} disabled={pending || !selectedSlot}>
              {pending ? <Loader2 className="size-4 animate-spin" /> : null}
              Confirm
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

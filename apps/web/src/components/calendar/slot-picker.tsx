"use client";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { InterviewSlot } from "@/types/api";

export function SlotPicker({
  slots,
  loading,
  selected,
  onSelect,
}: {
  slots: InterviewSlot[] | null;
  loading: boolean;
  selected: string | null;
  onSelect: (slot: string) => void;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-sm text-subtle">
        <Loader2 className="size-4 animate-spin" />
        Checking availability…
      </div>
    );
  }

  if (!slots) return null;

  return (
    <div className="grid grid-cols-3 gap-2">
      {slots.map((slot) => {
        const label = `${slot.start}-${slot.end}`;
        const isSelected = selected === label;
        return (
          <Button
            key={label}
            type="button"
            variant={isSelected ? "primary" : "outline"}
            size="sm"
            disabled={!slot.available}
            onClick={() => onSelect(label)}
            className={cn(!slot.available && "line-through opacity-40")}
          >
            {slot.start}
          </Button>
        );
      })}
    </div>
  );
}

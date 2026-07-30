"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { cn } from "@/lib/utils";
import type { PipelineStage } from "@/types/api";

const STAGES: { value: PipelineStage | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "applied", label: "Applied" },
  { value: "screening", label: "Screening" },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "hired", label: "Hired" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

function Tabs() {
  const router = useRouter();
  const params = useSearchParams();
  const current = params.get("stage") ?? "";

  return (
    <div className="mb-5 flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by stage">
      {STAGES.map((stage) => (
        <button
          key={stage.value || "all"}
          role="tab"
          aria-selected={current === stage.value}
          onClick={() => router.push(stage.value ? `?stage=${stage.value}` : "?")}
          className={cn(
            "rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors",
            current === stage.value
              ? "border-primary bg-primary/20 text-foreground"
              : "border-border bg-surface-2/40 text-muted hover:border-border-strong hover:text-foreground",
          )}
        >
          {stage.label}
        </button>
      ))}
    </div>
  );
}

export function StageFilter() {
  return (
    <Suspense fallback={null}>
      <Tabs />
    </Suspense>
  );
}

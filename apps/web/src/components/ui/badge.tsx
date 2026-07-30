import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";
import type { PipelineStage } from "@/types/api";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide",
  {
    variants: {
      tone: {
        neutral: "border-border bg-surface-2 text-muted",
        primary: "border-primary/40 bg-primary/15 text-[#c4b5fd]",
        accent: "border-accent/40 bg-accent/10 text-accent",
        success: "border-success/40 bg-success/10 text-success",
        warning: "border-warning/40 bg-warning/10 text-warning",
        danger: "border-danger/40 bg-danger/10 text-danger",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

const STAGE_TONE: Record<PipelineStage, BadgeProps["tone"]> = {
  applied: "neutral",
  screening: "accent",
  interview: "primary",
  offer: "warning",
  hired: "success",
  rejected: "danger",
  withdrawn: "neutral",
};

const STAGE_LABEL: Record<PipelineStage, string> = {
  applied: "Applied",
  screening: "Screening",
  interview: "Interview",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export function StageBadge({ stage }: { stage: PipelineStage }) {
  return <Badge tone={STAGE_TONE[stage]}>{STAGE_LABEL[stage]}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "published"
      ? "success"
      : status === "draft"
        ? "neutral"
        : status === "paused"
          ? "warning"
          : "danger";
  return <Badge tone={tone as BadgeProps["tone"]}>{status.toUpperCase()}</Badge>;
}

export { STAGE_LABEL };

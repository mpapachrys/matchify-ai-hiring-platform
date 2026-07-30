import * as React from "react";

import { cn } from "@/lib/utils";

const TONES = {
  primary: "text-[#a78bfa] bg-primary/15 border-primary/30",
  accent: "text-accent bg-accent/10 border-accent/30",
  success: "text-success bg-success/10 border-success/30",
  warning: "text-warning bg-warning/10 border-warning/30",
} as const;

export function StatTile({
  icon,
  value,
  label,
  tone = "primary",
  hint,
}: {
  icon: React.ReactNode;
  value: React.ReactNode;
  label: string;
  tone?: keyof typeof TONES;
  hint?: string;
}) {
  return (
    <div className="panel flex flex-col items-center gap-2 p-5 text-center">
      <div className={cn("grid size-10 place-items-center rounded-xl border", TONES[tone])}>
        {icon}
      </div>
      <p className="text-3xl font-bold tabular-nums text-foreground">{value}</p>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-subtle">{label}</p>
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

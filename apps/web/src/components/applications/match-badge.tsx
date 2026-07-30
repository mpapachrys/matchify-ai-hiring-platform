import { Loader2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Match, MatchStatus } from "@/types/api";

/**
 * The match confidence, computed by the AI team's graph and frozen at apply.
 *
 * Both audiences see the same percentage; the manager additionally gets the
 * factors behind it as a hover title.
 */

function toneForConfidence(confidence: number): "success" | "primary" | "warning" {
  if (confidence >= 0.75) return "success";
  if (confidence >= 0.5) return "primary";
  return "warning";
}

function Pending() {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-subtle"
      title="The match is being calculated"
    >
      <Loader2 className="size-3 animate-spin" />
      Calculating…
    </span>
  );
}

/** The percentage pill, shared by both views. `title` carries the factors on
 *  the manager side; the candidate passes none. */
function ScoreBadge({
  status,
  confidence,
  title,
  className,
}: {
  status: MatchStatus;
  confidence: number | null;
  title?: string;
  className?: string;
}) {
  if (status === "pending") return <Pending />;
  if (status !== "scored" || confidence === null) {
    return <span className="text-xs text-subtle">—</span>;
  }
  return (
    <Badge
      tone={toneForConfidence(confidence)}
      className={cn("gap-1", className)}
      title={title ?? "AI match confidence"}
    >
      <Sparkles className="size-3" />
      {Math.round(confidence * 100)}%
    </Badge>
  );
}

/** Manager view: percentage plus the factors as a hover title. */
export function ManagerMatchBadge({ match }: { match: Match }) {
  const factors = Object.entries(match.factors ?? {});
  const title = factors.length
    ? factors.map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`).join(" · ")
    : undefined;
  return <ScoreBadge status={match.status} confidence={match.confidence} title={title} />;
}

/** Candidate view: the same percentage, without the factors breakdown. */
export function CandidateMatchBadge({
  status,
  confidence,
  className,
}: {
  status: MatchStatus;
  confidence: number | null;
  className?: string;
}) {
  return <ScoreBadge status={status} confidence={confidence} className={className} />;
}

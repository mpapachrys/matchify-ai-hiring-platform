"use client";

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { GripVertical, Star } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ManagerMatchBadge } from "@/components/applications/match-badge";
import { Avatar } from "@/components/ui/misc";
import { ApiError, api } from "@/lib/api/client";
import { cn, relativeTime } from "@/lib/utils";
import type { ManagerApplication, PipelineStage } from "@/types/api";

const COLUMNS: { stage: PipelineStage; label: string; accent: string }[] = [
  { stage: "applied", label: "Applied", accent: "border-t-slate-500" },
  { stage: "screening", label: "Screening", accent: "border-t-cyan-400" },
  { stage: "interview", label: "Interview", accent: "border-t-violet-500" },
  { stage: "offer", label: "Offer", accent: "border-t-amber-400" },
  { stage: "hired", label: "Hired", accent: "border-t-emerald-400" },
  { stage: "rejected", label: "Rejected", accent: "border-t-rose-500" },
];

function ApplicantCard({
  application,
  dragging,
}: {
  application: ManagerApplication;
  dragging?: boolean;
}) {
  return (
    <div
      className={cn(
        "panel-solid p-3 transition-shadow",
        dragging ? "rotate-2 shadow-2xl ring-1 ring-primary" : "hover:border-primary/40",
      )}
    >
      <div className="flex items-start gap-2">
        <Avatar
          name={application.candidate_snapshot.full_name}
          src={application.candidate_snapshot.avatar_url}
          className="size-7"
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-foreground">
            {application.candidate_snapshot.full_name}
          </p>
          <p className="truncate text-[11px] text-subtle">
            {application.candidate_snapshot.headline ?? application.job_snapshot.title}
          </p>
        </div>
        {application.is_shortlisted ? (
          <Star className="size-3.5 shrink-0 fill-warning text-warning" />
        ) : null}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[11px] text-subtle">{relativeTime(application.applied_at)}</span>
        <ManagerMatchBadge match={application.match} />
      </div>
    </div>
  );
}

function DraggableCard({ application }: { application: ManagerApplication }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: application.id,
  });

  return (
    <div ref={setNodeRef} className={cn(isDragging && "opacity-40")}>
      <div className="group relative">
        <button
          type="button"
          {...listeners}
          {...attributes}
          aria-label={`Drag ${application.candidate_snapshot.full_name}`}
          className="absolute right-1 top-1 z-10 rounded p-1 text-subtle opacity-0 transition-opacity group-hover:opacity-100"
        >
          <GripVertical className="size-3.5" />
        </button>
        <Link href={`/manager/candidates/${application.candidate_id}`} className="block">
          <ApplicantCard application={application} />
        </Link>
      </div>
    </div>
  );
}

function Column({
  stage,
  label,
  accent,
  applications,
}: {
  stage: PipelineStage;
  label: string;
  accent: string;
  applications: ManagerApplication[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-72 shrink-0 flex-col rounded-xl border border-t-2 border-border bg-surface/50 transition-colors",
        accent,
        isOver && "border-primary bg-primary/10",
      )}
    >
      <div className="flex items-center justify-between px-3 py-2.5">
        <span className="text-xs font-bold uppercase tracking-wider text-foreground">{label}</span>
        <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-semibold text-muted">
          {applications.length}
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2 pt-0">
        {applications.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-subtle">Drop candidates here</p>
        ) : (
          applications.map((application) => (
            <DraggableCard key={application.id} application={application} />
          ))
        )}
      </div>
    </div>
  );
}

/**
 * Kanban with optimistic moves.
 *
 * The card jumps columns immediately and is rolled back if the PATCH fails —
 * a drag that visibly snaps back is clearer feedback than a spinner.
 */
export function PipelineBoard({ applications }: { applications: ManagerApplication[] }) {
  const router = useRouter();
  const [items, setItems] = React.useState(applications);
  const [activeId, setActiveId] = React.useState<string | null>(null);

  React.useEffect(() => setItems(applications), [applications]);

  const sensors = useSensors(
    // A small threshold keeps the card link clickable — a click is not a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  );

  const active = items.find((item) => item.id === activeId) ?? null;

  function onDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  async function onDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active: dragged, over } = event;
    if (!over) return;

    const id = String(dragged.id);
    const target = String(over.id) as PipelineStage;
    const current = items.find((item) => item.id === id);
    if (!current || current.stage === target) return;

    const previous = items;
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, stage: target } : item)),
    );

    try {
      await api.patch(`/applications/${id}/stage`, { stage: target });
      toast.success(`Moved to ${target}`);
      router.refresh();
    } catch (error) {
      setItems(previous);
      toast.error(error instanceof ApiError ? error.message : "Could not move candidate");
    }
  }

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-4">
        {COLUMNS.map((column) => (
          <Column
            key={column.stage}
            {...column}
            applications={items.filter((item) => item.stage === column.stage)}
          />
        ))}
      </div>

      <DragOverlay>
        {active ? (
          <div className="w-64">
            <ApplicantCard application={active} dragging />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

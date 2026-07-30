"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Archive, Eye, MoreHorizontal, Pencil, Send, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api/client";
import type { ManagerJob } from "@/types/api";

const itemClass =
  "flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-sm text-muted outline-none transition-colors data-[highlighted]:bg-surface-2 data-[highlighted]:text-foreground";

export function JobRowActions({ job }: { job: ManagerJob }) {
  const router = useRouter();
  const [pending, setPending] = React.useState(false);

  async function run(action: "publish" | "close", label: string) {
    setPending(true);
    try {
      await api.post(`/jobs/${job.id}/${action}`);
      toast.success(label);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Action failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        disabled={pending}
        className="rounded-lg p-2 text-subtle transition-colors hover:bg-surface-2 hover:text-foreground disabled:opacity-50"
        aria-label={`Actions for ${job.title}`}
      >
        <MoreHorizontal className="size-4" />
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="panel-solid z-50 min-w-48 p-1.5 shadow-2xl"
        >
          <DropdownMenu.Item asChild className={itemClass}>
            <Link href={`/manager/jobs/${job.id}/applicants`}>
              <Users className="size-4" /> View applicants
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Item asChild className={itemClass}>
            <Link href={`/manager/jobs/${job.id}/pipeline`}>
              <Eye className="size-4" /> Open pipeline
            </Link>
          </DropdownMenu.Item>

          {job.can_edit ? (
            <DropdownMenu.Item asChild className={itemClass}>
              <Link href={`/manager/jobs/${job.id}/edit`}>
                <Pencil className="size-4" /> Edit job
              </Link>
            </DropdownMenu.Item>
          ) : null}

          {job.can_edit && job.status !== "published" ? (
            <DropdownMenu.Item className={itemClass} onSelect={() => run("publish", "Job published")}>
              <Send className="size-4" /> Publish
            </DropdownMenu.Item>
          ) : null}

          {job.can_edit && job.status === "published" ? (
            <DropdownMenu.Item className={itemClass} onSelect={() => run("close", "Job closed")}>
              <Archive className="size-4" /> Close job
            </DropdownMenu.Item>
          ) : null}

          {!job.can_edit ? (
            <p className="px-2.5 py-2 text-xs text-subtle">
              Read-only — created by another manager
            </p>
          ) : null}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

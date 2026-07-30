"use client";

import { Download, FileText, PencilRuler, Sparkles } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { formatDate } from "@/lib/utils";
import type { UserDocument } from "@/types/api";

/**
 * The candidate's résumé, read-only.
 *
 * There is no upload here on purpose: the résumé is generated in the Resume
 * Builder, which is the single editing surface for a candidate's profile. Letting
 * them drop a stray PDF here would fork the source of truth. This page shows what
 * the builder produced and points back to it for any change.
 */
export function ResumePanel({ resumes }: { resumes: UserDocument[] }) {
  async function open(id: string) {
    try {
      const { url } = await api.get<{ url: string }>(`/documents/${id}/url`);
      window.open(url, "_blank", "noopener");
    } catch {
      toast.error("Could not open résumé");
    }
  }

  // Newest first; the primary résumé (the one applications attach) leads.
  const ordered = [...resumes].sort((a, b) => {
    if (a.is_primary !== b.is_primary) return a.is_primary ? -1 : 1;
    return b.uploaded_at.localeCompare(a.uploaded_at);
  });

  return (
    <div className="space-y-4">
      <Card className="border-primary/30">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-start gap-3">
            <PencilRuler className="mt-0.5 size-5 shrink-0 text-accent" />
            <div>
              <p className="text-sm font-semibold text-foreground">
                Your résumé lives in the Resume Builder
              </p>
              <p className="mt-0.5 text-xs text-muted">
                Create it, edit it, and regenerate the PDF there — no uploads on this page.
              </p>
            </div>
          </div>
          <Button asChild variant="primary" size="sm">
            <Link href="/candidate/resume-builder">
              <Sparkles className="size-4" /> Open Resume Builder
            </Link>
          </Button>
        </CardContent>
      </Card>

      {ordered.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <FileText className="mx-auto mb-3 size-6 text-subtle" />
            <p className="text-sm font-medium text-foreground">No résumé yet</p>
            <p className="mx-auto mt-1 max-w-sm text-xs text-subtle">
              Head to the Resume Builder to create one. It is attached automatically the first
              time you apply to a job.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-border/60">
              {ordered.map((doc) => (
                <li key={doc.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                  <FileText className="size-4 shrink-0 text-subtle" />
                  <div className="min-w-40 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                      {doc.filename}
                      {doc.is_primary ? <Badge tone="primary">Primary</Badge> : null}
                    </p>
                    <p className="text-xs text-subtle">Updated {formatDate(doc.uploaded_at)}</p>
                  </div>
                  <Button variant="ghost" size="icon" title="Open" onClick={() => open(doc.id)}>
                    <Download className="size-4" />
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

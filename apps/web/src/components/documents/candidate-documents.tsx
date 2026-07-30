"use client";

import { ExternalLink, FileText } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import type { UserDocument } from "@/types/api";

/**
 * The résumé(s) a candidate submitted with an application — the only file a
 * manager is allowed to open. Read-only: no verification, no other documents,
 * no other resume versions. The API enforces the same rule, so a crafted
 * request for anything else is refused regardless of this UI.
 */
export function CandidateDocuments({ documents }: { documents: UserDocument[] }) {
  async function open(id: string) {
    try {
      // Minted per click, expires in 15 minutes — cannot be forwarded into a
      // permanent leak.
      const { url } = await api.get<{ url: string }>(`/documents/${id}/url`);
      window.open(url, "_blank", "noopener");
    } catch {
      toast.error("Could not open résumé");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submitted résumé</CardTitle>
      </CardHeader>
      <CardContent className="p-0 pb-4">
        {documents.length === 0 ? (
          <p className="px-5 py-3 text-xs text-subtle">
            No résumé was attached to this candidate&rsquo;s applications.
          </p>
        ) : (
          <ul className="space-y-1">
            {documents.map((doc) => (
              <li key={doc.id} className="px-5 py-2">
                <button
                  onClick={() => open(doc.id)}
                  className="flex w-full items-center gap-2 text-left text-sm text-foreground hover:text-[#c4b5fd]"
                >
                  <FileText className="size-3.5 shrink-0 text-subtle" />
                  <span className="min-w-0 flex-1 truncate">{doc.filename}</span>
                  <ExternalLink className="size-3 shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

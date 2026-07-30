"use client";

import { Loader2, Lock, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";
import { titleCase } from "@/lib/utils";
import type { DocumentType, Organization } from "@/types/api";

const DOC_TYPES: DocumentType[] = [
  "resume",
  "passport",
  "degree",
  "mark_sheet",
  "certificate",
  "reference_letter",
];

export function OrganizationForm({
  org,
  canEdit,
}: {
  org: Organization;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [pending, setPending] = React.useState(false);
  const [form, setForm] = React.useState({
    name: org.name,
    website: org.website ?? "",
    description: org.description ?? "",
    industry: org.industry ?? "",
    size: org.size ?? "",
    country: org.headquarters.country ?? "",
    city: org.headquarters.city ?? "",
    require_cover_letter: org.hiring.require_cover_letter,
  });
  const [requiredDocs, setRequiredDocs] = React.useState<DocumentType[]>(
    org.hiring.required_documents,
  );

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    try {
      await api.patch<Organization>("/organization", {
        name: form.name,
        website: form.website || null,
        description: form.description || null,
        industry: form.industry || null,
        size: form.size || null,
        headquarters: {
          country: form.country || null,
          city: form.city || null,
          postal_code: org.headquarters.postal_code,
          address: org.headquarters.address,
        },
        hiring: {
          default_pipeline_stages: org.hiring.default_pipeline_stages,
          require_cover_letter: form.require_cover_letter,
          required_documents: requiredDocs,
        },
      });
      toast.success("Organization updated");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not save");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {!canEdit ? (
        <Card className="border-warning/30">
          <CardContent className="flex items-center gap-3 p-4 text-sm text-muted">
            <Lock className="size-4 shrink-0 text-warning" />
            Only an administrator can change organization settings. You have read access.
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Company profile</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Company name" htmlFor="name" required>
            <Input
              id="name"
              required
              disabled={!canEdit}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </Field>
          <Field label="Website" htmlFor="website">
            <Input
              id="website"
              disabled={!canEdit}
              value={form.website}
              onChange={(e) => set("website", e.target.value)}
            />
          </Field>
          <Field label="Description" htmlFor="description" className="sm:col-span-2">
            <Textarea
              id="description"
              rows={3}
              disabled={!canEdit}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </Field>
          <Field label="Industry" htmlFor="industry">
            <Input
              id="industry"
              disabled={!canEdit}
              value={form.industry}
              onChange={(e) => set("industry", e.target.value)}
            />
          </Field>
          <Field label="Company size" htmlFor="size">
            <Input
              id="size"
              disabled={!canEdit}
              placeholder="11-50"
              value={form.size}
              onChange={(e) => set("size", e.target.value)}
            />
          </Field>
          <Field label="Country" htmlFor="country">
            <Input
              id="country"
              disabled={!canEdit}
              value={form.country}
              onChange={(e) => set("country", e.target.value)}
            />
          </Field>
          <Field label="City" htmlFor="city">
            <Input
              id="city"
              disabled={!canEdit}
              value={form.city}
              onChange={(e) => set("city", e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hiring defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="mb-2 text-xs font-medium text-muted">
              Required verification documents
            </p>
            <div className="flex flex-wrap gap-2">
              {DOC_TYPES.map((doc) => {
                const selected = requiredDocs.includes(doc);
                return (
                  <button
                    key={doc}
                    type="button"
                    disabled={!canEdit}
                    aria-pressed={selected}
                    onClick={() =>
                      setRequiredDocs((prev) =>
                        selected ? prev.filter((d) => d !== doc) : [...prev, doc],
                      )
                    }
                    className={
                      selected
                        ? "rounded-full border border-primary bg-primary/20 px-3 py-1 text-xs font-semibold text-foreground disabled:opacity-60"
                        : "rounded-full border border-border bg-surface-2/40 px-3 py-1 text-xs text-muted hover:border-border-strong disabled:opacity-60"
                    }
                  >
                    {titleCase(doc)}
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-subtle">
              This list drives the verification checklist on every candidate dashboard.
            </p>
          </div>

          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={form.require_cover_letter}
              onChange={(e) => set("require_cover_letter", e.target.checked)}
              className="size-4 accent-[#8b5cf6]"
            />
            Require a cover letter on every application
          </label>
        </CardContent>
      </Card>

      {canEdit ? (
        <Button type="submit" variant="primary" size="lg" disabled={pending}>
          {pending ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
          Save organization
        </Button>
      ) : null}
    </form>
  );
}

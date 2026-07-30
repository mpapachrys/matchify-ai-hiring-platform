"use client";

import {
  AlertTriangle,
  Check,
  CheckCircle2,
  FileText,
  Loader2,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { ParseState, ParsedResumeData, ResumeDraft } from "@/types/api";

/**
 * Upload a CV, watch the AI read it, then choose what to keep.
 *
 * Pipeline, all of it visible in the modal:
 *   presign → direct PUT to storage → confirm (parse: true) → poll for the result
 *
 * The parse runs server-side in the background, so the upload request returns in
 * milliseconds and this component polls instead of holding a request open for
 * the length of a model call.
 *
 * Nothing is applied automatically. An LLM misreading a date is routine, and
 * silently overwriting a form someone filled in by hand is the one mistake they
 * could not undo — so the extraction is shown in full and the candidate decides.
 */

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 180_000;

/** Where the pipeline currently is. Drives both the stepper and the modal state. */
type Phase = "idle" | "uploading" | "saving" | "analysing" | "done" | "failed";

const STEPS: { phase: Phase; label: string; caption: string }[] = [
  { phase: "uploading", label: "Uploading your CV", caption: "Sent straight to secure storage" },
  { phase: "saving", label: "Saving the document", caption: "Recording it against your account" },
  { phase: "analysing", label: "Reading and analysing", caption: "Extracting the text, then the AI reads it" },
];

const PHASE_ORDER: Phase[] = ["uploading", "saving", "analysing"];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function countExtracted(data: ParsedResumeData | null): number {
  if (!data) return 0;
  let n = 0;
  for (const v of [
    data.full_name,
    data.headline,
    data.email,
    data.phone,
    data.summary,
    data.seniority,
    data.job_category,
    data.years_experience,
    data.location?.city || data.location?.country,
    data.links?.linkedin,
    data.links?.github,
    data.links?.portfolio,
  ]) {
    if (v) n++;
  }
  n += data.skills?.length ?? 0;
  n += (data.experience ?? []).reduce((sum, e) => sum + (e.skills?.length ?? 0), 0);
  n += data.experience?.length ?? 0;
  n += data.education?.length ?? 0;
  n += data.languages?.length ?? 0;
  n += data.certifications?.length ?? 0;
  const a = data.achievements;
  n +=
    (a?.career_highlights?.length ?? 0) +
    (a?.academic_distinctions?.length ?? 0) +
    (a?.awards_and_competitions?.length ?? 0) +
    (a?.projects_and_open_source?.length ?? 0);
  return n;
}

/**
 * Append entries from the CV that the draft doesn't already have.
 *
 * All-or-nothing on lists would make the feature useless: a profile with one
 * seeded role would silently discard all three roles the CV describes. Keying
 * on the identifying pair lets both sets coexist without duplicating a role the
 * candidate already entered by hand.
 */
function mergeList<T>(existing: T[], incoming: T[] | undefined, key: (item: T) => string): T[] {
  const seen = new Set(existing.map(key));
  const additions = (incoming ?? []).filter((item) => {
    const k = key(item);
    if (!k.trim() || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return [...existing, ...additions];
}

const norm = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

const mergeStrings = (existing: string[], incoming: string[] | undefined) =>
  mergeList(existing, incoming, (s) => norm(s));

/** Merge extraction into the draft. Only fills blanks — never clobbers typing. */
export function mergeIntoDraft(draft: ResumeDraft, data: ParsedResumeData): ResumeDraft {
  return {
    ...draft,
    full_name: draft.full_name || data.full_name || "",
    headline: draft.headline || data.headline || null,
    email: draft.email || data.email || null,
    phone: draft.phone || data.phone || null,
    city: draft.city || data.location?.city || null,
    country: draft.country || data.location?.country || null,
    summary: draft.summary || data.summary || null,
    // The model infers these from the work history; before the builder owned
    // the profile they were extracted and then thrown away.
    job_category: draft.job_category || data.job_category || null,
    seniority: draft.seniority || (data.seniority as ResumeDraft["seniority"]) || null,
    experience: mergeList(
      draft.experience,
      data.experience,
      (e) => `${norm(e.company)}|${norm(e.title)}`,
    ),
    education: mergeList(
      draft.education,
      data.education,
      (e) => `${norm(e.institution)}|${norm(e.degree)}`,
    ),
    languages: mergeList(draft.languages, data.languages, (l) => norm(l.name)),
    certifications: mergeList(
      draft.certifications,
      data.certifications,
      (c) => `${norm(c.name)}|${norm(c.issuer)}`,
    ),
    // Achievements append per bucket, de-duplicated on the text itself.
    achievements: {
      career_highlights: mergeStrings(
        draft.achievements.career_highlights,
        data.achievements?.career_highlights,
      ),
      academic_distinctions: mergeStrings(
        draft.achievements.academic_distinctions,
        data.achievements?.academic_distinctions,
      ),
      awards_and_competitions: mergeStrings(
        draft.achievements.awards_and_competitions,
        data.achievements?.awards_and_competitions,
      ),
      projects_and_open_source: mergeStrings(
        draft.achievements.projects_and_open_source,
        data.achievements?.projects_and_open_source,
      ),
    },
    links: {
      linkedin: draft.links.linkedin || data.links?.linkedin || null,
      github: draft.links.github || data.links?.github || null,
      portfolio: draft.links.portfolio || data.links?.portfolio || null,
    },
  };
}

export const ACHIEVEMENT_BUCKETS = [
  { key: "career_highlights", label: "Career highlights" },
  { key: "academic_distinctions", label: "Academic distinctions" },
  { key: "awards_and_competitions", label: "Awards & competitions" },
  { key: "projects_and_open_source", label: "Projects & open source" },
] as const;

// ── modal pieces ────────────────────────────────────────────────────────────

function Stepper({ phase }: { phase: Phase }) {
  const currentIndex = PHASE_ORDER.indexOf(phase);

  return (
    <ol className="space-y-3">
      {STEPS.map((step, index) => {
        const done = currentIndex > index || phase === "done";
        const active = currentIndex === index && phase !== "done";
        return (
          <li key={step.phase} className="flex items-start gap-3">
            <div
              className={cn(
                "mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border transition-colors",
                done && "border-success bg-success/20 text-success",
                active && "border-primary bg-primary/20 text-[#c4b5fd]",
                !done && !active && "border-border bg-surface-2 text-subtle",
              )}
            >
              {done ? (
                <Check className="size-3.5" />
              ) : active ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <span className="text-[10px] font-bold">{index + 1}</span>
              )}
            </div>
            <div className="min-w-0">
              <p
                className={cn(
                  "text-sm font-medium",
                  done || active ? "text-foreground" : "text-subtle",
                )}
              >
                {step.label}
              </p>
              <p className="text-xs text-subtle">{step.caption}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Row({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  if (!value) return null;
  return (
    <div className="flex gap-3 py-1.5 text-sm">
      <span className="w-24 shrink-0 text-xs text-subtle">{label}</span>
      <span className="min-w-0 flex-1 break-words text-foreground">
        {value}
        {hint ? <span className="ml-1.5 text-[11px] text-subtle">{hint}</span> : null}
      </span>
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-border/60 pt-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
        {title}
        {count != null ? ` (${count})` : ""}
      </p>
      {children}
    </div>
  );
}

function dateRange(start?: string | null, end?: string | null, current?: boolean) {
  const right = current ? "present" : (end ?? "");
  if (start && right) return `${start} → ${right}`;
  return start || right || "";
}

/** Everything the model returned, laid out so it can actually be checked. */
function Findings({ data }: { data: ParsedResumeData }) {
  const location = [data.location?.city, data.location?.country].filter(Boolean).join(", ");
  const inferred = "· inferred";

  return (
    <div className="space-y-3">
      <div>
        <Row label="Name" value={data.full_name} />
        <Row label="Headline" value={data.headline} />
        <Row label="Email" value={data.email} />
        <Row label="Phone" value={data.phone} />
        <Row label="Location" value={location} />
        <Row label="Category" value={data.job_category} hint={inferred} />
        <Row
          label="Seniority"
          value={
            data.seniority
              ? `${data.seniority}${data.years_experience ? ` · ${data.years_experience} years` : ""}`
              : null
          }
          hint={inferred}
        />
        <Row label="Summary" value={data.summary} />
      </div>

      {data.experience?.length ? (
        <Section title="Experience" count={data.experience.length}>
          <ul className="space-y-2">
            {data.experience.map((role, index) => (
              <li key={index} className="rounded-lg bg-surface-2/50 px-3 py-2">
                <p className="text-sm font-medium text-foreground">
                  {[role.title, role.company].filter(Boolean).join(" — ") || "Role"}
                </p>
                <p className="text-xs text-subtle">
                  {[dateRange(role.start_date, role.end_date, role.is_current), role.location]
                    .filter(Boolean)
                    .join("  ·  ")}
                </p>
                {role.skills?.length ? (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {role.skills.map((skill) => (
                      <Badge key={skill} tone="primary">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1.5 text-[11px] text-warning">
                    No skills found for this role — you'll need to add at least one.
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {data.education?.length ? (
        <Section title="Education" count={data.education.length}>
          <ul className="space-y-2">
            {data.education.map((entry, index) => (
              <li key={index} className="rounded-lg bg-surface-2/50 px-3 py-2">
                <p className="text-sm font-medium text-foreground">
                  {[entry.degree, entry.institution].filter(Boolean).join(" — ") || "Qualification"}
                </p>
                <p className="text-xs text-subtle">
                  {[dateRange(entry.start_date, entry.end_date), entry.grade]
                    .filter(Boolean)
                    .join("  ·  ")}
                </p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {data.skills?.length ? (
        <Section title="Also mentioned" count={data.skills.length}>
          <div className="flex flex-wrap gap-1.5">
            {data.skills.map((skill) => (
              <Badge key={skill}>{skill}</Badge>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-subtle">
            These weren&rsquo;t tied to a specific role in your CV. Add them to the roles where
            you used them.
          </p>
        </Section>
      ) : null}

      {data.certifications?.length ? (
        <Section title="Certifications" count={data.certifications.length}>
          <ul className="space-y-1.5">
            {data.certifications.map((cert, index) => (
              <li key={index} className="rounded-lg bg-surface-2/50 px-3 py-2">
                <p className="text-sm text-foreground">{cert.name}</p>
                <p className="text-xs text-subtle">
                  {[cert.issuer, cert.issued_year].filter(Boolean).join("  ·  ")}
                </p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {ACHIEVEMENT_BUCKETS.map(({ key, label }) => {
        const items = data.achievements?.[key] ?? [];
        return items.length ? (
          <Section key={key} title={label} count={items.length}>
            <ul className="space-y-1">
              {items.map((item, index) => (
                <li key={index} className="text-xs text-muted">
                  · {item}
                </li>
              ))}
            </ul>
          </Section>
        ) : null;
      })}

      {data.languages?.length ? (
        <Section title="Languages" count={data.languages.length}>
          <div className="flex flex-wrap gap-1.5">
            {data.languages.map((lang) => (
              <Badge key={lang.name} tone="accent">
                {lang.name}
                {lang.level ? ` · ${lang.level}` : ""}
              </Badge>
            ))}
          </div>
        </Section>
      ) : null}

      {data.links?.linkedin || data.links?.github || data.links?.portfolio ? (
        <Section title="Links">
          <div className="space-y-1">
            {(["linkedin", "github", "portfolio"] as const).map((key) =>
              data.links?.[key] ? (
                <p key={key} className="truncate text-xs text-accent">
                  {data.links[key]}
                </p>
              ) : null,
            )}
          </div>
        </Section>
      ) : null}
    </div>
  );
}

// ── main component ──────────────────────────────────────────────────────────

export function CvUpload({ onApply }: { onApply: (data: ParsedResumeData) => void }) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [open, setOpen] = React.useState(false);
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [fileInfo, setFileInfo] = React.useState<{ name: string; size: number } | null>(null);
  const [result, setResult] = React.useState<ParseState | null>(null);
  const [elapsed, setElapsed] = React.useState(0);

  // Guards the poll loop against running after unmount. It MUST be reset on
  // mount, not just set on unmount: React StrictMode mounts → unmounts →
  // remounts in development, so a cleanup-only version latches to `true` on the
  // throwaway first mount and every subsequent poll bails on its first tick —
  // the upload succeeds server-side and the UI silently shows nothing.
  const cancelled = React.useRef(false);

  React.useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const busy = phase === "uploading" || phase === "saving" || phase === "analysing";

  // Elapsed counter — a model call can run 30s, and a spinner with no number
  // reads as "stuck".
  React.useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    setElapsed(0);
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(id);
  }, [busy]);

  async function poll(documentId: string): Promise<ParseState | null> {
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (cancelled.current) return null;
      const state = await api.get<ParseState>(`/resume/documents/${documentId}/parse`);
      if (state.status === "done" || state.status === "failed") return state;
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    return null;
  }

  async function upload(file: File) {
    setFileInfo({ name: file.name, size: file.size });
    setResult(null);
    setPhase("uploading");
    setOpen(true);

    try {
      const contentType = file.type || "application/pdf";

      const presigned = await api.post<{ upload_url: string; object_key: string }>(
        "/documents/presign",
        {
          type: "resume",
          filename: file.name,
          content_type: contentType,
          size_bytes: file.size,
        },
      );

      const put = await fetch(presigned.upload_url, {
        method: "PUT",
        body: file,
        headers: { "content-type": contentType },
      });
      if (!put.ok) throw new Error("Upload to storage failed");

      setPhase("saving");

      const doc = await api.post<{ id: string }>("/documents/confirm", {
        type: "resume",
        object_key: presigned.object_key,
        filename: file.name,
        content_type: contentType,
        size_bytes: file.size,
        make_primary: false,
        parse: true,
      });

      setPhase("analysing");
      const state = await poll(doc.id);

      if (!state) {
        setResult({
          document_id: doc.id,
          filename: file.name,
          status: "failed",
          error: "Timed out waiting for the parser. Fill the form in manually.",
          model_version: null,
          data: null,
          started_at: null,
          completed_at: null,
        });
        setPhase("failed");
        return;
      }

      setResult(state);
      setPhase(state.status === "failed" ? "failed" : "done");
    } catch (error) {
      setResult({
        document_id: "",
        filename: file.name,
        status: "failed",
        error:
          error instanceof ApiError
            ? error.message
            : "Upload failed — check the file type and size.",
        model_version: null,
        data: null,
        started_at: null,
        completed_at: null,
      });
      setPhase("failed");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function close() {
    setOpen(false);
    setPhase("idle");
    setResult(null);
  }

  const extracted = countExtracted(result?.data ?? null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.doc,.docx"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
        }}
      />

      <div className="flex flex-col items-center gap-2">
        <Button
          type="button"
          variant="primary"
          size="lg"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
          {busy ? "Scanning your CV…" : "Upload your CV"}
        </Button>
        <p className="text-xs text-subtle">
          PDF or Word · we read it and fill the form in for you
        </p>
      </div>

      <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
        <DialogContent
          // Locked while work is in flight so a stray click can't abandon a
          // running job the user is waiting on.
          locked={busy}
          className="max-w-xl"
          title={
            phase === "done"
              ? "Review what we found"
              : phase === "failed"
                ? "We couldn't read that CV"
                : "Scanning your CV"
          }
          description={
            fileInfo ? `${fileInfo.name} · ${formatBytes(fileInfo.size)}` : undefined
          }
        >
          {busy ? (
            <div className="space-y-4">
              <Stepper phase={phase} />
              <div className="rounded-lg border border-primary/30 bg-primary/10 px-3 py-2.5">
                <p className="flex items-center justify-between text-xs text-[#c4b5fd]">
                  <span>Reading happens on our servers, not in your browser.</span>
                  <span className="tabular-nums font-semibold">{elapsed}s</span>
                </p>
                <p className="mt-1 text-xs text-subtle">
                  Usually 10–30 seconds. Please keep this open until it finishes.
                </p>
              </div>
            </div>
          ) : null}

          {phase === "failed" ? (
            <div className="space-y-4">
              <div className="flex gap-3 rounded-lg border border-danger/30 bg-danger/10 p-3">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
                <p className="text-sm text-danger">
                  {result?.error ?? "Something went wrong reading that file."}
                </p>
              </div>
              <p className="text-xs text-subtle">
                You can still fill the form in by hand — nothing about your CV upload is lost.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={close}>
                  Close
                </Button>
                <Button variant="primary" onClick={() => inputRef.current?.click()}>
                  <Upload className="size-4" /> Try another file
                </Button>
              </div>
            </div>
          ) : null}

          {phase === "done" ? (
            <div className="space-y-4">
              {/* The model identifier stays server-side. It is still recorded
                  on the document for auditability, but which vendor and model
                  read the CV is an implementation detail, not something the
                  candidate needs to evaluate. */}
              <p className="flex items-center gap-2 text-sm font-semibold text-success">
                <Sparkles className="size-4" />
                {extracted > 0
                  ? `Found ${extracted} ${extracted === 1 ? "detail" : "details"}`
                  : "Nothing could be extracted"}
              </p>

              {extracted > 0 && result?.data ? (
                <>
                  <div className="max-h-[45vh] overflow-y-auto rounded-lg border border-border bg-surface-2/30 p-3">
                    <Findings data={result.data} />
                  </div>

                  <p className="rounded-lg border border-border bg-surface-2/40 px-3 py-2 text-xs text-muted">
                    <strong className="text-foreground">Nothing has been saved yet.</strong>{" "}
                    Applying fills empty fields only — anything you have already typed stays as
                    it is, and roles from your CV are added alongside existing ones rather than
                    replacing them.
                  </p>
                </>
              ) : (
                <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
                  The file was read, but no usable details came back. It may be a scanned image
                  or an unusual layout — fill the form in manually.
                </p>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={close}>
                  <X className="size-4" /> Discard
                </Button>
                <Button
                  variant="primary"
                  disabled={extracted === 0}
                  onClick={() => {
                    if (result?.data) onApply(result.data);
                    close();
                    toast.success("Form filled in — review and edit before generating.");
                  }}
                >
                  <CheckCircle2 className="size-4" /> Apply to form
                </Button>
              </div>
            </div>
          ) : null}

          {phase === "idle" && !result ? (
            <p className="flex items-center gap-2 text-sm text-muted">
              <FileText className="size-4" /> Choose a file to begin.
            </p>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

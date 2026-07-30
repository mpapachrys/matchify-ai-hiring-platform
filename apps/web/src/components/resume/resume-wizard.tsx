"use client";

import {
  ArrowLeft,
  Check,
  Download,
  FileText,
  Loader2,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  TriangleAlert,
  X,
  User as UserIcon,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ACHIEVEMENT_BUCKETS, CvUpload, mergeIntoDraft } from "@/components/resume/cv-upload";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, Input, Select, Textarea } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type {
  DegreeLevel,
  DraftCertification,
  DraftEducation,
  DraftExperience,
  DraftIssue,
  DraftLanguage,
  LanguageProficiency,
  GeneratedResume,
  ParsedResumeData,
  ResumeDraft,
  ResumeTemplate,
  SeniorityLevel,
  WorkMode,
} from "@/types/api";

const SENIORITY: SeniorityLevel[] = ["intern", "junior", "mid", "senior", "lead", "principal"];
const DEGREE_LEVELS: DegreeLevel[] = [
  "High School",
  "Certificate",
  "Diploma",
  "Bachelor",
  "Master",
  "PhD",
];
const PROFICIENCY: LanguageProficiency[] = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"];
/** Must match INDUSTRIES in the API — the graph keys nodes on these strings. */
const INDUSTRIES = [
  "Fintech", "Banking", "Insurance", "E-commerce", "Retail", "Logistics",
  "Healthcare", "Biotech", "Education", "Gaming", "Media", "Telecommunications",
  "Energy", "Manufacturing", "Automotive", "Travel", "Real Estate", "Consulting",
  "Public Sector", "Non-profit", "Agency", "SaaS", "Tech",
];
const WORK_MODES: WorkMode[] = ["onsite", "hybrid", "remote"];
const CATEGORIES = [
  "Software Engineer",
  "Design",
  "Data",
  "Infrastructure",
  "Product",
  "Marketing",
  "Sales",
  "Operations",
];

const STEPS = [
  { id: 1, title: "Template Selection", caption: "Choose your resume template", icon: FileText },
  { id: 2, title: "Personal Information", caption: "Fill in your details", icon: Pencil },
  { id: 3, title: "Preview & Download", caption: "Edit, preview and download", icon: Download },
] as const;

const EMPTY_EXPERIENCE: DraftExperience = {
  company: "",
  title: "",
  start_date: "",
  end_date: "",
  is_current: false,
  location: "",
  description: "",
  skills: [],
  company_industry: null,
};

const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

function parseMonth(value: string | null | undefined): Date | null {
  if (!value || !MONTH_RE.test(value.trim())) return null;
  const [year, month] = value.trim().split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1));
}

/**
 * Total professional years from the role date ranges, mirroring the server.
 *
 * Overlapping roles are merged rather than summed — two jobs held at once for a
 * year is one year of experience, not two.
 */
function deriveYears(experience: DraftExperience[]): number | null {
  const now = new Date();
  const spans: [number, number][] = [];

  for (const role of experience) {
    const start = parseMonth(role.start_date);
    if (!start) continue;
    const end = role.is_current ? now : parseMonth(role.end_date);
    if (!end || end < start) continue;
    spans.push([start.getTime(), Math.min(end.getTime(), now.getTime())]);
  }
  if (!spans.length) return null;

  spans.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [spans[0]];
  for (const [start, end] of spans.slice(1)) {
    const last = merged[merged.length - 1];
    if (start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }

  const ms = merged.reduce((sum, [s, e]) => sum + (e - s), 0);
  return Math.round((ms / (1000 * 60 * 60 * 24 * 365.25)) * 10) / 10;
}

/** Mirrors `resume_service.validate_draft`; the server is still the guard. */
function findIssues(draft: ResumeDraft): DraftIssue[] {
  const issues: DraftIssue[] = [];

  if (!draft.full_name.trim()) {
    issues.push({ field: "full_name", index: null, message: "Add your full name." });
  }
  if (!draft.experience.length) {
    issues.push({
      field: "experience",
      index: null,
      message: "Add at least one role to your work history.",
    });
  }

  draft.experience.forEach((role, index) => {
    const label = role.title || role.company || `Role ${index + 1}`;
    if (!role.title?.trim())
      issues.push({ field: "title", index, message: `${label}: add a job title.` });
    if (!role.company?.trim())
      issues.push({ field: "company", index, message: `${label}: add the company.` });
    if (!role.skills.filter((s) => s.trim()).length)
      issues.push({
        field: "skills",
        index,
        message: `${label}: add at least one skill you used in this role.`,
      });
    if (!parseMonth(role.start_date))
      issues.push({
        field: "start_date",
        index,
        message: `${label}: add a start date (YYYY-MM).`,
      });
    if (!role.is_current) {
      const end = parseMonth(role.end_date);
      if (!end)
        issues.push({
          field: "end_date",
          index,
          message: `${label}: add an end date, or tick “I currently work here”.`,
        });
      else {
        const start = parseMonth(role.start_date);
        if (start && end < start)
          issues.push({
            field: "end_date",
            index,
            message: `${label}: the end date is before the start date.`,
          });
      }
    }
  });

  return issues;
}

const EMPTY_EDUCATION: DraftEducation = {
  institution: "",
  degree: "",
  degree_level: null,
  field: "",
  start_date: "",
  end_date: "",
  grade: "",
};

const EMPTY_CERTIFICATION: DraftCertification = {
  name: "",
  issuer: "",
  issued_year: null,
  credential_id: null,
};

const EMPTY_LANGUAGE: DraftLanguage = { name: "", level: "B2" };

/** Comma/Enter-separated skill chips, scoped to a single role. */
function SkillChips({
  value,
  onChange,
  id,
  error,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  id: string;
  error?: string;
}) {
  const [text, setText] = React.useState("");

  function commit(raw: string) {
    const added = raw
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    if (added.length) onChange(Array.from(new Set([...value, ...added])));
    setText("");
  }

  return (
    <div>
      {value.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {value.map((skill) => (
            <Badge key={skill} tone="primary" className="gap-1 pr-1">
              {skill}
              <button
                type="button"
                onClick={() => onChange(value.filter((s) => s !== skill))}
                className="rounded-full p-0.5 hover:bg-white/10"
                aria-label={`Remove ${skill}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
      <div className="flex gap-2">
        <Input
          id={id}
          value={text}
          aria-invalid={Boolean(error)}
          className={error ? "border-danger" : undefined}
          onChange={(e) => {
            // Typing a comma commits the chip, same as pressing Enter.
            if (e.target.value.includes(",")) commit(e.target.value);
            else setText(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit(text);
            }
          }}
          onBlur={() => commit(text)}
          placeholder="python, react, figma…"
        />
        <Button type="button" variant="outline" onClick={() => commit(text)}>
          <Plus className="size-4" />
        </Button>
      </div>
      <FieldError>{error}</FieldError>
    </div>
  );
}

function Stepper({ current }: { current: number }) {
  return (
    <ol className="mb-8 flex items-start justify-center gap-2 sm:gap-6">
      {STEPS.map((step, index) => {
        const done = current > step.id;
        const active = current === step.id;
        return (
          <li key={step.id} className="flex flex-1 items-start gap-2 sm:gap-4">
            <div className="flex min-w-0 flex-1 flex-col items-center text-center">
              <div
                aria-current={active ? "step" : undefined}
                className={cn(
                  "grid size-10 shrink-0 place-items-center rounded-full border transition-colors",
                  done && "border-success bg-success/20 text-success",
                  active && "border-primary bg-primary text-white shadow-lg shadow-primary/30",
                  !done && !active && "border-border bg-surface-2 text-subtle",
                )}
              >
                {done ? <Check className="size-4" /> : <step.icon className="size-4" />}
              </div>
              <p
                className={cn(
                  "mt-2 text-xs font-semibold",
                  active || done ? "text-foreground" : "text-subtle",
                )}
              >
                {step.title}
              </p>
              <p className="hidden text-[11px] text-subtle sm:block">{step.caption}</p>
            </div>
            {index < STEPS.length - 1 ? (
              <div
                aria-hidden
                className={cn(
                  "mt-5 hidden h-px flex-1 sm:block",
                  current > step.id ? "bg-success" : "bg-border",
                )}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function ListSection<T>({
  title,
  hint,
  items,
  emptyLabel,
  addLabel,
  onAdd,
  onRemove,
  render,
}: {
  title: string;
  hint?: string;
  items: T[];
  emptyLabel: string;
  addLabel: string;
  onAdd: () => void;
  onRemove: (index: number) => void;
  render: (item: T, index: number) => React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-lg font-bold text-foreground">{title}</h3>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus className="size-4" /> {addLabel}
        </Button>
      </div>
      {hint ? <p className="mb-3 text-xs text-subtle">{hint}</p> : null}

      {items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-surface-2/30 px-4 py-6 text-center text-sm text-subtle">
          {emptyLabel}
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div key={index} className="rounded-xl border border-border bg-surface-2/30 p-4">
              <div className="mb-3 flex items-center justify-between">
                <Badge tone="primary">#{index + 1}</Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemove(index)}
                  aria-label={`Remove ${title} entry ${index + 1}`}
                >
                  <Trash2 className="size-4 text-danger" />
                </Button>
              </div>
              {render(item, index)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ResumeWizard({
  templates,
  initialDraft,
  hasProfileData,
}: {
  templates: ResumeTemplate[];
  initialDraft: ResumeDraft;
  hasProfileData: boolean;
}) {
  const [step, setStep] = React.useState(1);
  const [template, setTemplate] = React.useState(templates[0]?.id ?? "professional");
  const [draft, setDraft] = React.useState<ResumeDraft>(initialDraft);
  const [showIssues, setShowIssues] = React.useState(false);
  const [generating, setGenerating] = React.useState(false);
  const [generated, setGenerated] = React.useState<GeneratedResume | null>(null);

  function set<K extends keyof ResumeDraft>(key: K, value: ResumeDraft[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  function applyParsed(data: ParsedResumeData) {
    setDraft((prev) => mergeIntoDraft(prev, data));
  }

  function patchExperience(index: number, patch: Partial<DraftExperience>) {
    setDraft((prev) => ({
      ...prev,
      experience: prev.experience.map((e, i) => (i === index ? { ...e, ...patch } : e)),
    }));
  }

  function patchCertification(index: number, patch: Partial<DraftCertification>) {
    setDraft((prev) => ({
      ...prev,
      certifications: prev.certifications.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    }));
  }

  function patchLanguage(index: number, patch: Partial<DraftLanguage>) {
    setDraft((prev) => ({
      ...prev,
      languages: prev.languages.map((l, i) => (i === index ? { ...l, ...patch } : l)),
    }));
  }

  /** Achievement buckets are edited as one line per entry. */
  function setBucket(key: keyof ResumeDraft["achievements"], text: string) {
    setDraft((prev) => ({
      ...prev,
      achievements: {
        ...prev.achievements,
        [key]: text.split("\n").map((line) => line.trim()).filter(Boolean),
      },
    }));
  }

  function patchEducation(index: number, patch: Partial<DraftEducation>) {
    setDraft((prev) => ({
      ...prev,
      education: prev.education.map((e, i) => (i === index ? { ...e, ...patch } : e)),
    }));
  }

  async function generate() {
    // Client-side first so the offending rows can be highlighted; the server
    // re-checks and is the actual guard.
    if (issues.length) {
      setShowIssues(true);
      toast.error(
        `${issues.length} ${issues.length === 1 ? "detail is" : "details are"} still missing.`,
      );
      document.getElementById("draft-issues")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    setGenerating(true);
    try {
      const result = await api.post<GeneratedResume>("/resume/generate", {
        draft,
        template,
        set_as_primary: true,
      });
      setGenerated(result);
      setStep(3);
      toast.success("Resume generated — profile updated and set as your primary resume.");
    } catch (error) {
      // The server validates independently; if it rejects something the client
      // let through, show its list rather than a generic failure.
      const detail = (error as { body?: { issues?: DraftIssue[] } })?.body?.issues;
      if (detail?.length) setShowIssues(true);
      toast.error(error instanceof ApiError ? error.message : "Could not generate the resume");
    } finally {
      setGenerating(false);
    }
  }

  const issues = React.useMemo(() => findIssues(draft), [draft]);
  const issuesFor = (index: number, field: string) =>
    showIssues ? issues.find((i) => i.index === index && i.field === field)?.message : undefined;
  const derivedYears = React.useMemo(() => deriveYears(draft.experience), [draft.experience]);

  async function download() {
    if (!generated) return;
    try {
      // Presigned links expire; mint a fresh one rather than reusing a stale URL.
      // `download=true` returns a save-to-disk link — a Download button that
      // opens a preview tab is not a download.
      const { url } = await api.get<{ url: string }>(
        `/documents/${generated.document_id}/url?download=true`,
      );
      window.location.href = url;
    } catch {
      toast.error("Could not open the file");
    }
  }

  // ── step 1 ────────────────────────────────────────────────────────────────
  if (step === 1) {
    return (
      <div>
        <Stepper current={1} />
        <Card>
          <CardContent className="p-6 pt-6 text-center">
            <h1 className="text-3xl font-bold text-foreground">Choose Your Resume Template</h1>
            <p className="mt-1 text-sm text-muted">
              Select a template that best represents your professional style
            </p>

            <div
              className={cn(
                "mx-auto mt-6 grid gap-4",
                // A lone card centred, rather than stretched across a 3-up grid.
                templates.length === 1 ? "max-w-xs" : "max-w-3xl sm:grid-cols-3",
              )}
            >
              {templates.map((option) => {
                const selected = template === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setTemplate(option.id)}
                    className={cn(
                      "relative rounded-xl border p-6 text-center transition-all",
                      selected
                        ? "border-primary bg-primary/15 shadow-lg shadow-primary/20"
                        : "border-border bg-surface-2/40 hover:border-border-strong",
                    )}
                  >
                    {selected ? (
                      <span className="absolute right-2 top-2">
                        <Badge tone="primary">Selected</Badge>
                      </span>
                    ) : null}
                    <div className="mx-auto mb-3 grid size-12 place-items-center rounded-xl bg-surface text-muted">
                      <UserIcon className="size-6" />
                    </div>
                    <p className="text-base font-bold text-foreground">{option.label}</p>
                    <p className="mt-1 text-xs text-muted">{option.description}</p>
                  </button>
                );
              })}
            </div>

            <Button variant="primary" size="lg" className="mt-8" onClick={() => setStep(2)}>
              Continue with {templates.find((t) => t.id === template)?.label ?? ""} template
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── step 3 ────────────────────────────────────────────────────────────────
  if (step === 3 && generated) {
    return (
      <div>
        <Stepper current={3} />
        <Card>
          <CardContent className="p-6 pt-6">
            <div className="mb-6 text-center">
              <div className="mx-auto mb-3 grid size-12 place-items-center rounded-2xl border border-success/30 bg-success/10 text-success">
                <Check className="size-6" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Your resume is ready</h1>
              <p className="mt-1 text-sm text-muted">
                Saved as <span className="text-foreground">{generated.filename}</span>
                {generated.is_primary
                  ? " and set as your primary resume — it will be attached to new applications."
                  : "."}
              </p>
            </div>

            <div className="mx-auto max-w-lg space-y-3">
              <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/40 p-4">
                <FileText className="size-8 shrink-0 text-[#a78bfa]" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {generated.filename}
                  </p>
                  <p className="text-xs text-subtle">
                    PDF · {templates.find((t) => t.id === template)?.label} template
                  </p>
                </div>
                <Button variant="primary" onClick={download}>
                  <Download className="size-4" /> Download
                </Button>
              </div>

              <div className="flex flex-wrap justify-center gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setGenerated(null);
                    setStep(2);
                  }}
                >
                  <ArrowLeft className="size-4" /> Edit details
                </Button>
                {/* Pointless with a single template — only offer it if there
                    is genuinely another one to try. */}
                {templates.length > 1 ? (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setGenerated(null);
                      setStep(1);
                    }}
                  >
                    Try another template
                  </Button>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── step 2 ────────────────────────────────────────────────────────────────
  return (
    <div>
      <Stepper current={2} />
      <Card>
        <CardContent className="space-y-8 p-6 pt-6">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-foreground">Personal Information</h1>
            <div className="mt-4">
              <CvUpload onApply={applyParsed} />
            </div>
            <div className="mx-auto my-4 flex max-w-xs items-center gap-3">
              <span className="h-px flex-1 bg-border" />
              <span className="text-xs text-subtle">Or</span>
              <span className="h-px flex-1 bg-border" />
            </div>
            <p className="text-sm text-muted">
              Fill in your details to generate a personalized resume
            </p>
            {hasProfileData ? (
              <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-success">
                <Sparkles className="size-3.5" /> Pre-filled from your profile
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full Name" htmlFor="full_name" required>
              <Input
                id="full_name"
                required
                value={draft.full_name}
                onChange={(e) => set("full_name", e.target.value)}
              />
            </Field>
            <Field label="Professional headline" htmlFor="headline">
              <Input
                id="headline"
                placeholder="Senior Software Engineer"
                value={draft.headline ?? ""}
                onChange={(e) => set("headline", e.target.value)}
              />
            </Field>
            <Field label="Email address" htmlFor="r_email">
              <Input
                id="r_email"
                type="email"
                value={draft.email ?? ""}
                onChange={(e) => set("email", e.target.value)}
              />
            </Field>
            <Field label="Phone number" htmlFor="r_phone">
              <Input
                id="r_phone"
                value={draft.phone ?? ""}
                onChange={(e) => set("phone", e.target.value)}
              />
            </Field>
            <Field label="City" htmlFor="r_city">
              <Input
                id="r_city"
                value={draft.city ?? ""}
                onChange={(e) => set("city", e.target.value)}
              />
            </Field>
            <Field label="Country" htmlFor="r_country">
              <Input
                id="r_country"
                value={draft.country ?? ""}
                onChange={(e) => set("country", e.target.value)}
              />
            </Field>
            <Field label="Professional summary" htmlFor="r_summary" className="sm:col-span-2">
              <Textarea
                id="r_summary"
                rows={3}
                value={draft.summary ?? ""}
                onChange={(e) => set("summary", e.target.value)}
                placeholder="Two or three sentences on what you do and what you're looking for."
              />
            </Field>
          </div>

          <ListSection
            title="Certifications"
            hint="Professional certifications, with the body that issued them"
            addLabel="Add Certification"
            emptyLabel="No certifications added yet."
            items={draft.certifications}
            onAdd={() => set("certifications", [...draft.certifications, { ...EMPTY_CERTIFICATION }])}
            onRemove={(index) =>
              set(
                "certifications",
                draft.certifications.filter((_, i) => i !== index),
              )
            }
            render={(cert, index) => (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Name" htmlFor={`cert-name-${index}`} className="sm:col-span-2">
                  <Input
                    id={`cert-name-${index}`}
                    placeholder="AWS Certified Machine Learning — Specialty"
                    value={cert.name}
                    onChange={(e) => patchCertification(index, { name: e.target.value })}
                  />
                </Field>
                <Field label="Issuer" htmlFor={`cert-issuer-${index}`}>
                  <Input
                    id={`cert-issuer-${index}`}
                    placeholder="Amazon Web Services"
                    value={cert.issuer ?? ""}
                    onChange={(e) => patchCertification(index, { issuer: e.target.value })}
                  />
                </Field>
                <Field label="Year issued" htmlFor={`cert-year-${index}`}>
                  <Input
                    id={`cert-year-${index}`}
                    type="number"
                    min={1950}
                    max={2100}
                    placeholder="2022"
                    value={cert.issued_year ?? ""}
                    onChange={(e) =>
                      patchCertification(index, {
                        issued_year: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  />
                </Field>
              </div>
            )}
          />

          <ListSection
            title="Languages"
            addLabel="Add Language"
            emptyLabel="No languages added yet."
            hint="Proficiency uses the CEFR scale"
            items={draft.languages}
            onAdd={() => set("languages", [...draft.languages, { ...EMPTY_LANGUAGE }])}
            onRemove={(index) =>
              set(
                "languages",
                draft.languages.filter((_, i) => i !== index),
              )
            }
            render={(lang, index) => (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Language" htmlFor={`lang-name-${index}`}>
                  <Input
                    id={`lang-name-${index}`}
                    placeholder="English"
                    value={lang.name}
                    onChange={(e) => patchLanguage(index, { name: e.target.value })}
                  />
                </Field>
                <Field label="Proficiency" htmlFor={`lang-level-${index}`}>
                  <Select
                    id={`lang-level-${index}`}
                    value={lang.level ?? "B2"}
                    onChange={(e) =>
                      patchLanguage(index, { level: e.target.value as LanguageProficiency })
                    }
                  >
                    {PROFICIENCY.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            )}
          />

          <div>
            <h3 className="text-lg font-bold text-foreground">Achievements</h3>
            <p className="mb-3 text-xs text-subtle">
              One per line. Concrete and measurable beats general — &ldquo;cut inference
              latency 40%&rdquo; is worth more than &ldquo;improved performance&rdquo;.
            </p>
            <div className="space-y-4">
              {ACHIEVEMENT_BUCKETS.map(({ key, label }) => (
                <Field key={key} label={label} htmlFor={`ach-${key}`}>
                  <Textarea
                    id={`ach-${key}`}
                    rows={2}
                    value={draft.achievements[key].join("\n")}
                    onChange={(e) => setBucket(key, e.target.value)}
                  />
                </Field>
              ))}
            </div>
          </div>

          <div>
            <h3 className="mb-3 text-lg font-bold text-foreground">Links</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              {(["linkedin", "github", "portfolio"] as const).map((key) => (
                <Field key={key} label={key[0].toUpperCase() + key.slice(1)} htmlFor={`link-${key}`}>
                  <Input
                    id={`link-${key}`}
                    placeholder={`https://${key === "portfolio" ? "yoursite.com" : key + ".com/you"}`}
                    value={draft.links[key] ?? ""}
                    onChange={(e) =>
                      set("links", { ...draft.links, [key]: e.target.value || null })
                    }
                  />
                </Field>
              ))}
            </div>
          </div>

          {/* Not printed on the resume — these drive job matching and are what
              hiring managers filter on, so the builder has to own them. */}
          <div>
            <h3 className="text-lg font-bold text-foreground">How you want to be matched</h3>
            <p className="mb-3 text-xs text-subtle">
              Not printed on your resume — used to match you with relevant jobs.
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Job category" htmlFor="r_category">
                <Select
                  id="r_category"
                  value={draft.job_category ?? ""}
                  onChange={(e) => set("job_category", e.target.value || null)}
                >
                  <option value="">Select a category</option>
                  {CATEGORIES.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field label="Seniority level" htmlFor="r_seniority">
                <Select
                  id="r_seniority"
                  value={draft.seniority ?? ""}
                  onChange={(e) =>
                    set("seniority", (e.target.value || null) as ResumeDraft["seniority"])
                  }
                >
                  <option value="">Select a level</option>
                  {SENIORITY.map((level) => (
                    <option key={level} value={level}>
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </option>
                  ))}
                </Select>
              </Field>

              {/* Derived, not entered: the role dates are the single source, so
                  this can never contradict the work history. */}
              <div id="r_years" data-years={derivedYears ?? ""}>
                <p className="mb-1.5 block text-xs font-medium text-muted">
                  Years of experience
                </p>
                <div className="flex h-10 items-center rounded-lg border border-border bg-surface-2/30 px-3 text-sm">
                  {derivedYears != null ? (
                    <span className="text-foreground">
                      {derivedYears} years
                      <span className="ml-2 text-xs text-subtle">
                        calculated from your roles
                      </span>
                    </span>
                  ) : (
                    <span className="text-subtle">Add role dates to calculate</span>
                  )}
                </div>
              </div>

              <div className="flex items-end pb-2.5">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
                  <input
                    type="checkbox"
                    checked={draft.open_to_relocate}
                    onChange={(e) => set("open_to_relocate", e.target.checked)}
                    className="size-4 accent-[#8b5cf6]"
                  />
                  Open to relocation
                </label>
              </div>

              <div className="sm:col-span-2">
                <p className="mb-2 text-xs font-medium text-muted">Preferred work modes</p>
                <div className="flex flex-wrap gap-2">
                  {WORK_MODES.map((mode) => {
                    const selected = draft.work_modes.includes(mode);
                    return (
                      <button
                        key={mode}
                        type="button"
                        aria-pressed={selected}
                        onClick={() =>
                          set(
                            "work_modes",
                            selected
                              ? draft.work_modes.filter((m) => m !== mode)
                              : [...draft.work_modes, mode],
                          )
                        }
                        className={cn(
                          "rounded-full border px-3 py-1 text-xs transition-colors",
                          selected
                            ? "border-primary bg-primary/20 font-semibold text-foreground"
                            : "border-border bg-surface-2/40 text-muted hover:border-border-strong",
                        )}
                      >
                        {mode.charAt(0).toUpperCase() + mode.slice(1)}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          <ListSection
            title="Work Experience"
            hint="Add your roles newest first. Dates and skills are required for every role — they are what your years of experience and job matches are calculated from."
            addLabel="Add Experience"
            emptyLabel="No work experience added yet."
            items={draft.experience}
            onAdd={() => set("experience", [...draft.experience, { ...EMPTY_EXPERIENCE }])}
            onRemove={(index) =>
              set(
                "experience",
                draft.experience.filter((_, i) => i !== index),
              )
            }
            render={(role, index) => (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Job title"
                  htmlFor={`exp-title-${index}`}
                  required
                  error={issuesFor(index, "title")}
                >
                  <Input
                    id={`exp-title-${index}`}
                    value={role.title ?? ""}
                    onChange={(e) => patchExperience(index, { title: e.target.value })}
                  />
                </Field>
                <Field
                  label="Company"
                  htmlFor={`exp-company-${index}`}
                  required
                  error={issuesFor(index, "company")}
                >
                  <Input
                    id={`exp-company-${index}`}
                    value={role.company ?? ""}
                    onChange={(e) => patchExperience(index, { company: e.target.value })}
                  />
                </Field>
                <Field
                  label="Start (YYYY-MM)"
                  htmlFor={`exp-start-${index}`}
                  required
                  error={issuesFor(index, "start_date")}
                >
                  <Input
                    id={`exp-start-${index}`}
                    placeholder="2019-03"
                    value={role.start_date ?? ""}
                    onChange={(e) => patchExperience(index, { start_date: e.target.value })}
                  />
                </Field>
                <Field
                  label="End (YYYY-MM)"
                  htmlFor={`exp-end-${index}`}
                  required={!role.is_current}
                  error={issuesFor(index, "end_date")}
                >
                  <Input
                    id={`exp-end-${index}`}
                    placeholder="2023-06"
                    disabled={role.is_current}
                    value={role.is_current ? "" : (role.end_date ?? "")}
                    onChange={(e) => patchExperience(index, { end_date: e.target.value })}
                  />
                </Field>
                <Field label="Location" htmlFor={`exp-loc-${index}`}>
                  <Input
                    id={`exp-loc-${index}`}
                    value={role.location ?? ""}
                    onChange={(e) => patchExperience(index, { location: e.target.value })}
                  />
                </Field>
                <Field
                  label="Company industry"
                  htmlFor={`exp-industry-${index}`}
                  hint="Helps match you with similar employers"
                >
                  <Select
                    id={`exp-industry-${index}`}
                    value={role.company_industry ?? ""}
                    onChange={(e) =>
                      patchExperience(index, { company_industry: e.target.value || null })
                    }
                  >
                    <option value="">Select an industry</option>
                    {INDUSTRIES.map((industry) => (
                      <option key={industry} value={industry}>
                        {industry}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="flex items-end pb-2.5">
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
                    <input
                      type="checkbox"
                      checked={role.is_current}
                      onChange={(e) =>
                        patchExperience(index, {
                          is_current: e.target.checked,
                          end_date: e.target.checked ? null : role.end_date,
                        })
                      }
                      className="size-4 accent-[#8b5cf6]"
                    />
                    I currently work here
                  </label>
                </div>
                <Field label="What you did" htmlFor={`exp-desc-${index}`} className="sm:col-span-2">
                  <Textarea
                    id={`exp-desc-${index}`}
                    rows={2}
                    value={role.description ?? ""}
                    onChange={(e) => patchExperience(index, { description: e.target.value })}
                  />
                </Field>

                <Field
                  label="Skills used in this role"
                  htmlFor={`exp-skills-${index}`}
                  required
                  className="sm:col-span-2"
                  hint="Comma-separated. These are what job matching runs on."
                >
                  <SkillChips
                    id={`exp-skills-${index}`}
                    value={role.skills}
                    error={issuesFor(index, "skills")}
                    onChange={(next) => patchExperience(index, { skills: next })}
                  />
                </Field>
              </div>
            )}
          />

          <ListSection
            title="Education"
            addLabel="Add Education"
            emptyLabel="No education added yet."
            items={draft.education}
            onAdd={() => set("education", [...draft.education, { ...EMPTY_EDUCATION }])}
            onRemove={(index) =>
              set(
                "education",
                draft.education.filter((_, i) => i !== index),
              )
            }
            render={(entry, index) => (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Degree" htmlFor={`edu-degree-${index}`}>
                  <Input
                    id={`edu-degree-${index}`}
                    value={entry.degree ?? ""}
                    onChange={(e) => patchEducation(index, { degree: e.target.value })}
                  />
                </Field>
                <Field label="Institution" htmlFor={`edu-inst-${index}`}>
                  <Input
                    id={`edu-inst-${index}`}
                    value={entry.institution ?? ""}
                    onChange={(e) => patchEducation(index, { institution: e.target.value })}
                  />
                </Field>
                <Field
                  label="Level"
                  htmlFor={`edu-level-${index}`}
                  hint="Normalized so it can be compared across CVs"
                >
                  <Select
                    id={`edu-level-${index}`}
                    value={entry.degree_level ?? ""}
                    onChange={(e) =>
                      patchEducation(index, {
                        degree_level: (e.target.value || null) as DegreeLevel | null,
                      })
                    }
                  >
                    <option value="">Select a level</option>
                    {DEGREE_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Field of study" htmlFor={`edu-field-${index}`}>
                  <Input
                    id={`edu-field-${index}`}
                    value={entry.field ?? ""}
                    onChange={(e) => patchEducation(index, { field: e.target.value })}
                  />
                </Field>
                <Field label="Grade" htmlFor={`edu-grade-${index}`}>
                  <Input
                    id={`edu-grade-${index}`}
                    value={entry.grade ?? ""}
                    onChange={(e) => patchEducation(index, { grade: e.target.value })}
                  />
                </Field>
                <Field label="Start (YYYY-MM)" htmlFor={`edu-start-${index}`}>
                  <Input
                    id={`edu-start-${index}`}
                    placeholder="2013-09"
                    value={entry.start_date ?? ""}
                    onChange={(e) => patchEducation(index, { start_date: e.target.value })}
                  />
                </Field>
                <Field label="End (YYYY-MM)" htmlFor={`edu-end-${index}`}>
                  <Input
                    id={`edu-end-${index}`}
                    placeholder="2018-07"
                    value={entry.end_date ?? ""}
                    onChange={(e) => patchEducation(index, { end_date: e.target.value })}
                  />
                </Field>
              </div>
            )}
          />

          {showIssues && issues.length > 0 ? (
            <div
              id="draft-issues"
              className="rounded-xl border border-danger/30 bg-danger/10 p-4"
              role="alert"
            >
              <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-danger">
                <TriangleAlert className="size-4" />
                {issues.length} {issues.length === 1 ? "detail" : "details"} still needed
              </p>
              <ul className="space-y-1">
                {issues.map((issue, i) => (
                  <li key={i} className="text-xs text-danger">
                    · {issue.message}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-muted">
                If your CV didn&rsquo;t include these, fill them in above — they are what your
                years of experience and job matches are calculated from.
              </p>
            </div>
          ) : null}

          {/* No opt-in checkbox: the builder is the only way to edit a profile,
              so making the save optional would let someone leave with an empty
              profile without realising it. */}
          <p className="flex items-start gap-2 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5 text-xs text-muted">
            <Sparkles className="mt-0.5 size-3.5 shrink-0 text-accent" />
            <span>
              Generating also updates your Matchify profile — this is what hiring managers see
              when you apply.
            </span>
          </p>
        </CardContent>

        <CardContent className="flex flex-wrap gap-3 border-t border-border/60 pt-5">
          <Button variant="outline" size="lg" className="flex-1" onClick={() => setStep(1)}>
            <ArrowLeft className="size-4" /> Back
          </Button>
          <Button
            variant="primary"
            size="lg"
            className="flex-1"
            disabled={generating}
            onClick={generate}
          >
            {generating ? <Loader2 className="size-4 animate-spin" /> : <FileText className="size-4" />}
            {generating ? "Generating…" : "Generate Resume"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

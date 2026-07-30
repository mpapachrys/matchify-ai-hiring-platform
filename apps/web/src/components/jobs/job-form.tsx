"use client";

import { Loader2, Plus, Save, X } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { ApiError, api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  NICE_TO_HAVE_WEIGHTS,
  type DegreeLevel,
  type EmploymentType,
  type ImportanceLevel,
  type LanguageProficiency,
  type MandatoryRequirements,
  type ManagerJob,
  type NiceToHave,
  type SeniorityLevel,
  type WorkMode,
} from "@/types/api";

const DEGREE_LEVELS: DegreeLevel[] = [
  "High School",
  "Certificate",
  "Diploma",
  "Bachelor",
  "Master",
  "PhD",
];
const PROFICIENCY: LanguageProficiency[] = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"];
const IMPORTANCE: { value: ImportanceLevel; label: string }[] = [
  { value: "nice", label: "Nice to have" },
  { value: "important", label: "Important" },
  { value: "critical", label: "Critical" },
];
/** Must match INDUSTRIES in the API — the graph keys nodes on these strings. */
const INDUSTRIES = [
  "Fintech", "Banking", "Insurance", "E-commerce", "Retail", "Logistics",
  "Healthcare", "Biotech", "Education", "Gaming", "Media", "Telecommunications",
  "Energy", "Manufacturing", "Automotive", "Travel", "Real Estate", "Consulting",
  "Public Sector", "Non-profit", "Agency", "SaaS", "Tech",
];

/** Nearest importance level for a stored weight. */
function levelFor(weight: number): ImportanceLevel {
  return (
    (Object.entries(NICE_TO_HAVE_WEIGHTS) as [ImportanceLevel, number][]).sort(
      (a, b) => Math.abs(a[1] - weight) - Math.abs(b[1] - weight),
    )[0]?.[0] ?? "important"
  );
}

const SENIORITY: SeniorityLevel[] = ["intern", "junior", "mid", "senior", "lead", "principal"];
const WORK_MODES: WorkMode[] = ["onsite", "hybrid", "remote"];
const EMPLOYMENT: EmploymentType[] = [
  "full_time",
  "part_time",
  "contract",
  "internship",
  "temporary",
];
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

function ListEditor({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = React.useState("");

  function add() {
    const value = draft.trim();
    if (value) onChange([...items, value]);
    setDraft("");
  }

  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-muted">{label}</p>
      {items.length > 0 ? (
        <ul className="mb-2 space-y-1.5">
          {items.map((item, index) => (
            <li
              key={`${item}-${index}`}
              className="flex items-start gap-2 rounded-lg border border-border bg-surface-2/40 px-3 py-2 text-sm text-foreground"
            >
              <span className="flex-1">{item}</span>
              <button
                type="button"
                onClick={() => onChange(items.filter((_, i) => i !== index))}
                className="text-subtle hover:text-danger"
                aria-label={`Remove "${item}"`}
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          aria-label={label}
        />
        <Button type="button" variant="outline" onClick={add}>
          <Plus className="size-4" />
        </Button>
      </div>
    </div>
  );
}

export function JobForm({ job }: { job?: ManagerJob }) {
  const router = useRouter();
  const editing = Boolean(job);
  const [pending, setPending] = React.useState(false);

  const [form, setForm] = React.useState({
    title: job?.title ?? "",
    description: job?.description ?? "",
    job_category: job?.job_category ?? "",
    seniority: job?.seniority ?? "mid",
    employment_type: job?.employment_type ?? "full_time",
    work_mode: job?.work_mode ?? "onsite",
    country: job?.location.country ?? "",
    city: job?.location.city ?? "",
    openings: job?.openings ?? 1,
    salary_min: job?.salary?.min?.toString() ?? "",
    salary_max: job?.salary?.max?.toString() ?? "",
    salary_public: job?.salary?.is_public ?? true,
  });
  const [responsibilities, setResponsibilities] = React.useState<string[]>(
    job?.responsibilities ?? [],
  );

  // Structured requirements replace the old free-text lists: one source of
  // truth, rendered as prose on the job page and consumed directly by matching.
  const [mandatory, setMandatory] = React.useState<MandatoryRequirements>(
    job?.mandatory ?? {
      min_years_total_experience: null,
      max_years_total_experience: null,
      education: [],
      skills: [],
      languages: [],
    },
  );
  const [niceToHave, setNiceToHave] = React.useState<NiceToHave>(
    job?.nice_to_have ?? { skills: [], certifications: [], preferred_industries: [] },
  );
  const [reqSkillDraft, setReqSkillDraft] = React.useState("");
  const [niceSkillDraft, setNiceSkillDraft] = React.useState("");

  const slugify = (name: string) => name.trim().toLowerCase();

  function addRequiredSkill() {
    const name = reqSkillDraft.trim();
    const slug = slugify(name);
    if (!slug || mandatory.skills.some((s) => s.slug === slug)) return setReqSkillDraft("");
    setMandatory((prev) => ({
      ...prev,
      skills: [...prev.skills, { slug, name, min_years: null }],
    }));
    setReqSkillDraft("");
  }

  function addNiceSkill() {
    const name = niceSkillDraft.trim();
    const slug = slugify(name);
    if (!slug || niceToHave.skills.some((s) => s.slug === slug)) return setNiceSkillDraft("");
    setNiceToHave((prev) => ({
      ...prev,
      skills: [...prev.skills, { slug, name, weight: NICE_TO_HAVE_WEIGHTS.important }],
    }));
    setNiceSkillDraft("");
  }

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function payload(status: "draft" | "published") {
    const hasSalary = form.salary_min || form.salary_max;
    return {
      title: form.title,
      description: form.description,
      job_category: form.job_category || null,
      seniority: form.seniority,
      employment_type: form.employment_type,
      work_mode: form.work_mode,
      location: {
        country: form.country || null,
        city: form.city || null,
        is_remote: form.work_mode === "remote",
      },
      openings: Number(form.openings) || 1,
      responsibilities,
      mandatory,
      nice_to_have: niceToHave,
      salary: hasSalary
        ? {
            min: form.salary_min ? Number(form.salary_min) : null,
            max: form.salary_max ? Number(form.salary_max) : null,
            currency: "EUR",
            period: "year",
            is_public: form.salary_public,
          }
        : null,
      status,
    };
  }

  async function submit(status: "draft" | "published") {
    if (form.title.trim().length < 3) {
      toast.error("Give the role a title of at least 3 characters");
      return;
    }
    setPending(true);
    try {
      if (editing && job) {
        await api.patch<ManagerJob>(`/jobs/${job.id}`, payload(status));
        toast.success(status === "published" ? "Job published" : "Job saved");
      } else {
        await api.post<ManagerJob>("/jobs", payload(status));
        toast.success(status === "published" ? "Job published" : "Draft saved");
      }
      router.push("/manager/jobs");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not save job");
      setPending(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit("published");
      }}
      className="space-y-4"
    >
      <Card>
        <CardHeader>
          <CardTitle>Role basics</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Job title" htmlFor="title" required className="sm:col-span-2">
            <Input
              id="title"
              required
              minLength={3}
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="Senior Full-Stack Engineer"
            />
          </Field>

          <Field label="Description" htmlFor="description" className="sm:col-span-2">
            <Textarea
              id="description"
              rows={5}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="What the role is, who it works with, and what success looks like."
            />
          </Field>

          <Field label="Category" htmlFor="job_category">
            <Select
              id="job_category"
              value={form.job_category}
              onChange={(e) => set("job_category", e.target.value)}
            >
              <option value="">Select a category</option>
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Seniority" htmlFor="seniority">
            <Select
              id="seniority"
              value={form.seniority}
              onChange={(e) => set("seniority", e.target.value as SeniorityLevel)}
            >
              {SENIORITY.map((level) => (
                <option key={level} value={level}>
                  {level.charAt(0).toUpperCase() + level.slice(1)}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Employment type" htmlFor="employment_type">
            <Select
              id="employment_type"
              value={form.employment_type}
              onChange={(e) => set("employment_type", e.target.value as EmploymentType)}
            >
              {EMPLOYMENT.map((type) => (
                <option key={type} value={type}>
                  {type.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase())}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Work mode" htmlFor="work_mode">
            <Select
              id="work_mode"
              value={form.work_mode}
              onChange={(e) => set("work_mode", e.target.value as WorkMode)}
            >
              {WORK_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Country" htmlFor="country">
            <Input id="country" value={form.country} onChange={(e) => set("country", e.target.value)} />
          </Field>

          <Field label="City" htmlFor="city">
            <Input id="city" value={form.city} onChange={(e) => set("city", e.target.value)} />
          </Field>

          <Field label="Openings" htmlFor="openings">
            <Input
              id="openings"
              type="number"
              min={1}
              max={999}
              value={form.openings}
              onChange={(e) => set("openings", Number(e.target.value))}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Must have</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-xs text-subtle">
            Hard requirements. A candidate either meets these or does not — they gate the
            match rather than scoring it.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Minimum years of experience"
              htmlFor="min_years"
              hint="Compared against the candidate's total, with overlapping roles merged"
            >
              <Input
                id="min_years"
                type="number"
                min={0}
                max={40}
                step={0.5}
                value={mandatory.min_years_total_experience ?? ""}
                onChange={(e) =>
                  setMandatory((prev) => ({
                    ...prev,
                    min_years_total_experience: e.target.value ? Number(e.target.value) : null,
                  }))
                }
              />
            </Field>
            <Field
              label="Maximum years"
              htmlFor="max_years"
              hint="Only for roles that are deliberately junior"
            >
              <Input
                id="max_years"
                type="number"
                min={0}
                max={40}
                step={0.5}
                value={mandatory.max_years_total_experience ?? ""}
                onChange={(e) =>
                  setMandatory((prev) => ({
                    ...prev,
                    max_years_total_experience: e.target.value ? Number(e.target.value) : null,
                  }))
                }
              />
            </Field>
          </div>

          {/* Required skills — each with its own minimum duration. */}
          <div>
            <p className="mb-1 text-xs font-medium text-muted">Required skills</p>
            <p className="mb-2 text-xs text-subtle">
              Set a minimum duration per skill; it is matched against how long the candidate
              actually used it.
            </p>
            {mandatory.skills.length === 0 ? (
              <p className="mb-2 text-xs text-subtle">No required skills yet.</p>
            ) : (
              <div className="mb-3 space-y-2">
                {mandatory.skills.map((skill, index) => (
                  <div
                    key={skill.slug}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-2/30 px-3 py-2"
                  >
                    <span className="min-w-24 flex-1 text-sm text-foreground">{skill.name}</span>
                    <label className="flex items-center gap-1.5 text-xs text-subtle">
                      min
                      <Input
                        id={`req-skill-years-${index}`}
                        type="number"
                        min={0}
                        max={40}
                        step={0.5}
                        className="h-8 w-20"
                        value={skill.min_years ?? ""}
                        onChange={(e) =>
                          setMandatory((prev) => ({
                            ...prev,
                            skills: prev.skills.map((s, i) =>
                              i === index
                                ? { ...s, min_years: e.target.value ? Number(e.target.value) : null }
                                : s,
                            ),
                          }))
                        }
                      />
                      yrs
                    </label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${skill.name}`}
                      onClick={() =>
                        setMandatory((prev) => ({
                          ...prev,
                          skills: prev.skills.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      <X className="size-4 text-danger" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                id="req-skill-add"
                value={reqSkillDraft}
                onChange={(e) => setReqSkillDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addRequiredSkill();
                  }
                }}
                placeholder="Python, SQL, React…"
                aria-label="Add a required skill"
              />
              <Button type="button" variant="outline" onClick={addRequiredSkill}>
                <Plus className="size-4" /> Add
              </Button>
            </div>
          </div>

          {/* Education */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium text-muted">Required education</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setMandatory((prev) => ({
                    ...prev,
                    education: [...prev.education, { degree_level: null, field_of_study: "" }],
                  }))
                }
              >
                <Plus className="size-4" /> Add
              </Button>
            </div>
            {mandatory.education.length === 0 ? (
              <p className="text-xs text-subtle">No education requirement.</p>
            ) : (
              <div className="space-y-2">
                {mandatory.education.map((entry, index) => (
                  <div key={index} className="flex flex-wrap items-end gap-2">
                    <div className="min-w-36 flex-1">
                      <Select
                        id={`req-degree-${index}`}
                        aria-label="Degree level"
                        value={entry.degree_level ?? ""}
                        onChange={(e) =>
                          setMandatory((prev) => ({
                            ...prev,
                            education: prev.education.map((x, i) =>
                              i === index
                                ? { ...x, degree_level: (e.target.value || null) as DegreeLevel | null }
                                : x,
                            ),
                          }))
                        }
                      >
                        <option value="">Any level</option>
                        {DEGREE_LEVELS.map((level) => (
                          <option key={level} value={level}>
                            {level}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div className="min-w-36 flex-1">
                      <Input
                        id={`req-field-${index}`}
                        aria-label="Field of study"
                        placeholder="Computer Science"
                        value={entry.field_of_study ?? ""}
                        onChange={(e) =>
                          setMandatory((prev) => ({
                            ...prev,
                            education: prev.education.map((x, i) =>
                              i === index ? { ...x, field_of_study: e.target.value } : x,
                            ),
                          }))
                        }
                      />
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove education requirement ${index + 1}`}
                      onClick={() =>
                        setMandatory((prev) => ({
                          ...prev,
                          education: prev.education.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      <X className="size-4 text-danger" />
                    </Button>
                  </div>
                ))}
                <p className="text-[11px] text-subtle">
                  Levels are ordered — a Master satisfies a Bachelor requirement.
                </p>
              </div>
            )}
          </div>

          {/* Languages */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium text-muted">Required languages</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setMandatory((prev) => ({
                    ...prev,
                    languages: [...prev.languages, { language: "", min_proficiency: "B2" }],
                  }))
                }
              >
                <Plus className="size-4" /> Add
              </Button>
            </div>
            {mandatory.languages.length === 0 ? (
              <p className="text-xs text-subtle">No language requirement.</p>
            ) : (
              <div className="space-y-2">
                {mandatory.languages.map((lang, index) => (
                  <div key={index} className="flex flex-wrap items-end gap-2">
                    <div className="min-w-36 flex-1">
                      <Input
                        id={`req-lang-${index}`}
                        aria-label="Language"
                        placeholder="English"
                        value={lang.language}
                        onChange={(e) =>
                          setMandatory((prev) => ({
                            ...prev,
                            languages: prev.languages.map((x, i) =>
                              i === index ? { ...x, language: e.target.value } : x,
                            ),
                          }))
                        }
                      />
                    </div>
                    <div className="w-32">
                      <Select
                        id={`req-lang-level-${index}`}
                        aria-label="Minimum proficiency"
                        value={lang.min_proficiency}
                        onChange={(e) =>
                          setMandatory((prev) => ({
                            ...prev,
                            languages: prev.languages.map((x, i) =>
                              i === index
                                ? { ...x, min_proficiency: e.target.value as LanguageProficiency }
                                : x,
                            ),
                          }))
                        }
                      >
                        {PROFICIENCY.map((level) => (
                          <option key={level} value={level}>
                            {level}+
                          </option>
                        ))}
                      </Select>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove language requirement ${index + 1}`}
                      onClick={() =>
                        setMandatory((prev) => ({
                          ...prev,
                          languages: prev.languages.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      <X className="size-4 text-danger" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Nice to have</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-xs text-subtle">
            These raise a candidate&rsquo;s score rather than gating it.
          </p>

          <div>
            <p className="mb-2 text-xs font-medium text-muted">Preferred skills</p>
            {niceToHave.skills.length === 0 ? (
              <p className="mb-2 text-xs text-subtle">No preferred skills yet.</p>
            ) : (
              <div className="mb-3 space-y-2">
                {niceToHave.skills.map((skill, index) => (
                  <div
                    key={skill.slug}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-2/30 px-3 py-2"
                  >
                    <span className="min-w-24 flex-1 text-sm text-foreground">{skill.name}</span>
                    <div className="w-36">
                      <Select
                        id={`nice-skill-weight-${index}`}
                        aria-label={`Importance of ${skill.name}`}
                        value={levelFor(skill.weight)}
                        onChange={(e) =>
                          setNiceToHave((prev) => ({
                            ...prev,
                            skills: prev.skills.map((s, i) =>
                              i === index
                                ? {
                                    ...s,
                                    weight:
                                      NICE_TO_HAVE_WEIGHTS[e.target.value as ImportanceLevel],
                                  }
                                : s,
                            ),
                          }))
                        }
                      >
                        {IMPORTANCE.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${skill.name}`}
                      onClick={() =>
                        setNiceToHave((prev) => ({
                          ...prev,
                          skills: prev.skills.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      <X className="size-4 text-danger" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                id="nice-skill-add"
                value={niceSkillDraft}
                onChange={(e) => setNiceSkillDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addNiceSkill();
                  }
                }}
                placeholder="Docker, Neo4j, PyTorch…"
                aria-label="Add a preferred skill"
              />
              <Button type="button" variant="outline" onClick={addNiceSkill}>
                <Plus className="size-4" /> Add
              </Button>
            </div>
          </div>

          <ListEditor
            label="Preferred certifications"
            items={niceToHave.certifications}
            onChange={(items) => setNiceToHave((prev) => ({ ...prev, certifications: items }))}
            placeholder="AWS Certified Machine Learning — Specialty"
          />

          <div>
            <p className="mb-2 text-xs font-medium text-muted">Preferred industries</p>
            <div className="flex flex-wrap gap-2">
              {INDUSTRIES.map((industry) => {
                const selected = niceToHave.preferred_industries.includes(industry);
                return (
                  <button
                    key={industry}
                    type="button"
                    aria-pressed={selected}
                    onClick={() =>
                      setNiceToHave((prev) => ({
                        ...prev,
                        preferred_industries: selected
                          ? prev.preferred_industries.filter((i) => i !== industry)
                          : [...prev.preferred_industries, industry],
                      }))
                    }
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs transition-colors",
                      selected
                        ? "border-primary bg-primary/20 font-semibold text-foreground"
                        : "border-border bg-surface-2/40 text-muted hover:border-border-strong",
                    )}
                  >
                    {industry}
                  </button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <ListEditor
            label="Responsibilities"
            items={responsibilities}
            onChange={setResponsibilities}
            placeholder="Own features end to end…"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Compensation</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <Field label="Minimum (EUR / year)" htmlFor="salary_min">
            <Input
              id="salary_min"
              type="number"
              min={0}
              step={1000}
              value={form.salary_min}
              onChange={(e) => set("salary_min", e.target.value)}
            />
          </Field>
          <Field label="Maximum (EUR / year)" htmlFor="salary_max">
            <Input
              id="salary_max"
              type="number"
              min={0}
              step={1000}
              value={form.salary_max}
              onChange={(e) => set("salary_max", e.target.value)}
            />
          </Field>
          <div className="flex items-end pb-2.5">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={form.salary_public}
                onChange={(e) => set("salary_public", e.target.checked)}
                className="size-4 accent-[#8b5cf6]"
              />
              Show to candidates
            </label>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" size="lg" disabled={pending}>
          {pending ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
          {editing ? "Save & publish" : "Publish job"}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="lg"
          disabled={pending}
          onClick={() => void submit("draft")}
        >
          Save as draft
        </Button>
        <Button type="button" variant="ghost" size="lg" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

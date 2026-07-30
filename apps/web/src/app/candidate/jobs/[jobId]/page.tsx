import { ArrowLeft, Building2, Calendar, MapPin, Users } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ApplyDialog } from "@/components/jobs/apply-dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, serverFetch, serverFetchOrNull } from "@/lib/api/server";
import { formatDate, formatSalary, titleCase } from "@/lib/utils";
import type { CandidateProfile, Job } from "@/types/api";

export const metadata = { title: "Job details" };

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold text-foreground">{title}</h2>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-muted">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;

  let job: Job;
  try {
    job = await serverFetch<Job>(`/jobs/${jobId}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const profile = await serverFetchOrNull<CandidateProfile>("/candidates/me/profile");
  // Turn the structured requirements into the sentences a candidate reads.
  const mustHave: string[] = [];
  if (job.mandatory.min_years_total_experience != null) {
    mustHave.push(
      `${job.mandatory.min_years_total_experience}+ years of professional experience`,
    );
  }
  if (job.mandatory.max_years_total_experience != null) {
    mustHave.push(`No more than ${job.mandatory.max_years_total_experience} years of experience`);
  }
  for (const entry of job.mandatory.education) {
    const parts = [entry.degree_level, entry.field_of_study].filter(Boolean).join(" in ");
    if (parts) mustHave.push(`${parts} (or higher)`);
  }
  for (const lang of job.mandatory.languages) {
    mustHave.push(`${lang.language} at ${lang.min_proficiency} or above`);
  }

  const salary = formatSalary(job.salary);
  const location = job.location.is_remote
    ? "Remote"
    : [job.location.city, job.location.country].filter(Boolean).join(", ") || "—";

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        href="/candidate/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to jobs
      </Link>

      <Card>
        <div className="bg-gradient-to-r from-primary/20 to-transparent p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{job.title}</h1>
              <p className="mt-1 text-sm text-muted">{job.job_category ?? "General"}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Badge tone="primary">{titleCase(job.seniority)}</Badge>
                <Badge tone="accent">{titleCase(job.work_mode)}</Badge>
                <Badge>{titleCase(job.employment_type)}</Badge>
              </div>
            </div>
            <ApplyDialog
              jobId={job.id}
              jobTitle={job.title}
              hasApplied={job.has_applied}
              hasResume={Boolean(profile?.primary_resume_id)}
            />
          </div>
        </div>

        <CardContent className="grid gap-4 border-t border-border/60 pt-5 sm:grid-cols-4">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-subtle">Location</p>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-foreground">
              <MapPin className="size-3.5 text-accent" /> {location}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-subtle">Openings</p>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-foreground">
              <Building2 className="size-3.5 text-accent" /> {job.openings}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-subtle">Applicants</p>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-foreground">
              <Users className="size-3.5 text-accent" /> {job.applications_count}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-subtle">Posted</p>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-foreground">
              <Calendar className="size-3.5 text-accent" />{" "}
              {formatDate(job.published_at ?? job.created_at)}
            </p>
          </div>
        </CardContent>

        {salary ? (
          <CardContent className="pt-0">
            <p className="text-lg font-bold text-success">{salary}</p>
          </CardContent>
        ) : null}
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>About this role</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="whitespace-pre-line text-sm leading-relaxed text-muted">
            {job.description}
          </p>
          <Section title="What you'll do" items={job.responsibilities} />
          {/* Rendered from the structured requirements — there is no separate
              prose copy to drift out of step with what matching actually uses. */}
          {mustHave.length > 0 ? (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-foreground">
                What we&rsquo;re looking for
              </h2>
              <ul className="space-y-1.5">
                {mustHave.map((line, index) => (
                  <li key={index} className="flex gap-2 text-sm text-muted">
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-primary" />
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {job.mandatory.skills.length > 0 ? (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-foreground">Required skills</h2>
              <div className="flex flex-wrap gap-1.5">
                {job.mandatory.skills.map((skill) => (
                  <Badge key={skill.slug} tone="primary">
                    {skill.name}
                    {skill.min_years ? ` · ${skill.min_years}+ yrs` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          {job.nice_to_have.skills.length > 0 ||
          job.nice_to_have.certifications.length > 0 ||
          job.nice_to_have.preferred_industries.length > 0 ? (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-foreground">Nice to have</h2>
              <div className="flex flex-wrap gap-1.5">
                {[...job.nice_to_have.skills]
                  .sort((a, b) => b.weight - a.weight)
                  .map((skill) => (
                    <Badge key={skill.slug} tone={skill.weight >= 1 ? "accent" : "neutral"}>
                      {skill.name}
                    </Badge>
                  ))}
                {job.nice_to_have.certifications.map((cert) => (
                  <Badge key={cert}>{cert}</Badge>
                ))}
              </div>
              {job.nice_to_have.preferred_industries.length > 0 ? (
                <p className="mt-2 text-xs text-subtle">
                  Background in {job.nice_to_have.preferred_industries.join(", ")} is a plus.
                </p>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

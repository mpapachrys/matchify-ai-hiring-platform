import { Building2, Clock, MapPin, Users } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { formatSalary, relativeTime, titleCase } from "@/lib/utils";
import type { Job } from "@/types/api";

export function JobCard({ job, href }: { job: Job; href: string }) {
  const salary = formatSalary(job.salary);
  const location = job.location.is_remote
    ? "Remote"
    : [job.location.city, job.location.country].filter(Boolean).join(", ") || "—";

  return (
    <Link
      href={href}
      className="panel group block p-5 transition-all hover:border-primary/50 hover:bg-surface-2/60"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground group-hover:text-[#c4b5fd]">
            {job.title}
          </h3>
          <p className="mt-0.5 text-xs text-subtle">{job.job_category ?? "General"}</p>
        </div>
        {job.has_applied ? <Badge tone="success">Applied</Badge> : null}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <MapPin className="size-3.5" /> {location}
        </span>
        <span className="flex items-center gap-1.5">
          <Building2 className="size-3.5" /> {titleCase(job.employment_type)}
        </span>
        <span className="flex items-center gap-1.5">
          <Users className="size-3.5" /> {job.applications_count} applicants
        </span>
        <span className="flex items-center gap-1.5">
          <Clock className="size-3.5" /> {relativeTime(job.published_at ?? job.created_at)}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge tone="primary">{titleCase(job.seniority)}</Badge>
        <Badge tone="accent">{titleCase(job.work_mode)}</Badge>
        {job.skills_required.slice(0, 4).map((skill) => (
          <Badge key={skill}>{skill}</Badge>
        ))}
        {job.skills_required.length > 4 ? (
          <Badge>+{job.skills_required.length - 4}</Badge>
        ) : null}
      </div>

      {salary ? (
        <p className="mt-3 text-sm font-semibold text-success">{salary}</p>
      ) : null}
    </Link>
  );
}

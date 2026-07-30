import {
  Briefcase,
  FileText,
  GraduationCap,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, EmptyState, Progress } from "@/components/ui/misc";
import { formatDate, titleCase } from "@/lib/utils";
import type { CandidateProfile } from "@/types/api";

/**
 * Read-only. The Resume Builder is the single editing surface for a profile —
 * two forms writing the same fields is exactly the ambiguity this removes.
 * Everything here links back to the builder rather than offering inputs.
 */
export function ProfileView({ profile }: { profile: CandidateProfile }) {
  const location = [profile.location.city, profile.location.country].filter(Boolean).join(", ");
  const hasAnything =
    profile.headline ||
    profile.summary ||
    profile.skills.length ||
    profile.experience.length ||
    profile.education.length;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-start gap-4 p-6">
          <Avatar name={profile.full_name} src={profile.avatar_url} className="size-16 text-lg" />
          <div className="min-w-56 flex-1">
            <h2 className="text-xl font-bold text-foreground">{profile.full_name}</h2>
            <p className="text-sm text-muted">{profile.headline ?? "No headline yet"}</p>

            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <Mail className="size-3.5 text-accent" /> {profile.email}
              </span>
              {location ? (
                <span className="flex items-center gap-1.5">
                  <MapPin className="size-3.5 text-accent" /> {location}
                </span>
              ) : null}
              {profile.years_experience != null ? (
                <span className="flex items-center gap-1.5">
                  <Briefcase className="size-3.5 text-accent" /> {profile.years_experience} years
                </span>
              ) : null}
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {profile.seniority ? (
                <Badge tone="primary">{titleCase(profile.seniority)}</Badge>
              ) : null}
              {profile.job_category ? <Badge tone="accent">{profile.job_category}</Badge> : null}
              {profile.open_to_relocate ? <Badge>Open to relocate</Badge> : null}
              {profile.work_modes.map((mode) => (
                <Badge key={mode}>{titleCase(mode)}</Badge>
              ))}
            </div>
          </div>

          <Button asChild variant="primary">
            <Link href="/candidate/resume-builder">
              <Pencil className="size-4" /> Edit in Resume Builder
            </Link>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-4 p-5">
          <div className="min-w-56 flex-1">
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="text-xs text-muted">Profile completion</span>
              <span className="text-sm font-semibold text-foreground">
                {profile.completion_percent}%
              </span>
            </div>
            <Progress value={profile.completion_percent} />
          </div>
          {profile.completion_percent < 100 ? (
            <Button asChild variant="outline" size="sm">
              <Link href="/candidate/resume-builder">
                <Sparkles className="size-4" /> Fill the gaps
              </Link>
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {!hasAnything ? (
        <Card>
          <EmptyState
            icon={<FileText className="size-5" />}
            title="Your profile is empty"
            description="Build it in the Resume Builder — upload your CV and it fills itself in, or type it out once."
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/candidate/resume-builder">Open Resume Builder</Link>
              </Button>
            }
          />
        </Card>
      ) : null}

      {profile.summary ? (
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-line text-sm leading-relaxed text-muted">
              {profile.summary}
            </p>
          </CardContent>
        </Card>
      ) : null}

      {profile.experience.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Experience</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {profile.experience.map((role, index) => (
              <div key={index} className="border-l-2 border-primary/40 pl-4">
                <p className="text-sm font-semibold text-foreground">{role.title}</p>
                <p className="text-xs text-muted">
                  {role.company}
                  {role.location ? ` · ${role.location}` : ""}
                </p>
                <p className="mt-0.5 text-xs text-subtle">
                  {formatDate(role.start_date)} —{" "}
                  {role.is_current ? "Present" : formatDate(role.end_date)}
                </p>
                {role.description ? (
                  <p className="mt-1.5 text-sm text-muted">{role.description}</p>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {profile.education.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Education</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {profile.education.map((entry, index) => (
              <div key={index} className="flex gap-3">
                <GraduationCap className="mt-0.5 size-4 shrink-0 text-accent" />
                <div>
                  <p className="text-sm font-semibold text-foreground">{entry.degree}</p>
                  <p className="text-xs text-muted">{entry.institution}</p>
                  <p className="text-xs text-subtle">
                    {formatDate(entry.start_date)} — {formatDate(entry.end_date)}
                    {entry.grade ? ` · ${entry.grade}` : ""}
                  </p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {profile.skills.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Skills</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {profile.skills.map((skill) => (
              <Badge key={skill} tone="primary">
                {skill}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {profile.languages.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Languages</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {profile.languages.map((lang) => (
              <Badge key={lang.name} tone="accent">
                {lang.name}
                {lang.level ? ` · ${lang.level}` : ""}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {profile.links.linkedin || profile.links.github || profile.links.portfolio ? (
        <Card>
          <CardHeader>
            <CardTitle>Links</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {(["linkedin", "github", "portfolio"] as const).map((key) =>
              profile.links[key] ? (
                <a
                  key={key}
                  href={profile.links[key] as string}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-sm text-accent hover:underline"
                >
                  {profile.links[key]}
                </a>
              ) : null,
            )}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-5">
          <p className="flex items-center gap-2 text-xs text-subtle">
            <Phone className="size-3.5" />
            Name, email and phone are part of your account — change them in Settings.
          </p>
          <Button asChild variant="ghost" size="sm">
            <Link href="/candidate/settings">Account settings</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

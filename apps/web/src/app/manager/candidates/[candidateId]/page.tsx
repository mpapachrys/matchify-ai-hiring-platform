import { ArrowLeft, Briefcase, GraduationCap, Mail, MapPin, Phone } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CandidateDocuments } from "@/components/documents/candidate-documents";
import { Badge, StageBadge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, PageHeader } from "@/components/ui/misc";
import { ApiError, serverFetch, serverFetchOrNull } from "@/lib/api/server";
import { formatDate, titleCase } from "@/lib/utils";
import type {
  CandidateProfile,
  ManagerApplication,
  Page,
  UserDocument,
} from "@/types/api";

export const metadata = { title: "Candidate" };

export default async function CandidateDetailPage({
  params,
}: {
  params: Promise<{ candidateId: string }>;
}) {
  const { candidateId } = await params;

  // The API refuses this unless the candidate has applied to one of our jobs —
  // there is no candidate directory to browse.
  let profile: CandidateProfile;
  try {
    profile = await serverFetch<CandidateProfile>(`/candidates/${candidateId}/profile`);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 403 || error.status === 404)) notFound();
    throw error;
  }

  const [documents, applications] = await Promise.all([
    serverFetchOrNull<UserDocument[]>(`/documents/candidate/${candidateId}`),
    serverFetch<Page<ManagerApplication>>("/applications/manage?page_size=200"),
  ]);

  const theirApplications = applications.items.filter(
    (application) => application.candidate_id === candidateId,
  );

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        href="/manager/applicants"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to applicants
      </Link>

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-start gap-4 p-6">
          <Avatar name={profile.full_name} src={profile.avatar_url} className="size-16 text-lg" />
          <div className="min-w-56 flex-1">
            <h1 className="text-xl font-bold text-foreground">{profile.full_name}</h1>
            <p className="text-sm text-muted">{profile.headline ?? "—"}</p>

            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <Mail className="size-3.5 text-accent" /> {profile.email}
              </span>
              {profile.location.city || profile.location.country ? (
                <span className="flex items-center gap-1.5">
                  <MapPin className="size-3.5 text-accent" />
                  {[profile.location.city, profile.location.country].filter(Boolean).join(", ")}
                </span>
              ) : null}
              {profile.years_experience != null ? (
                <span className="flex items-center gap-1.5">
                  <Briefcase className="size-3.5 text-accent" />
                  {profile.years_experience} years experience
                </span>
              ) : null}
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {profile.seniority ? (
                <Badge tone="primary">{titleCase(profile.seniority)}</Badge>
              ) : null}
              {profile.job_category ? <Badge tone="accent">{profile.job_category}</Badge> : null}
              {profile.open_to_relocate ? <Badge>Open to relocate</Badge> : null}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
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
                      </p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Applications</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-0 pb-4">
              {theirApplications.map((application) => (
                <div
                  key={application.id}
                  className="flex items-center justify-between gap-2 px-5 py-2"
                >
                  <Link
                    href={`/manager/jobs/${application.job_id}/applicants`}
                    className="min-w-0 flex-1 truncate text-sm text-foreground hover:text-[#c4b5fd]"
                  >
                    {application.job_snapshot.title}
                  </Link>
                  <StageBadge stage={application.stage} />
                </div>
              ))}
            </CardContent>
          </Card>

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

          <CandidateDocuments documents={documents ?? []} />
        </div>
      </div>
    </div>
  );
}

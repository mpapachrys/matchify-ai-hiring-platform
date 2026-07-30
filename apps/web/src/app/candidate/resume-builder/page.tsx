import { ResumeWizard } from "@/components/resume/resume-wizard";
import { serverFetch } from "@/lib/api/server";
import type { ResumeDraftSeed, ResumeTemplate } from "@/types/api";

export const metadata = { title: "Resume Builder" };

export default async function ResumeBuilderPage() {
  // Both are independent reads — fetch together rather than waterfalling.
  const [templates, seed] = await Promise.all([
    serverFetch<ResumeTemplate[]>("/resume/templates"),
    serverFetch<ResumeDraftSeed>("/resume/draft"),
  ]);

  return (
    <div className="mx-auto max-w-4xl">
      <ResumeWizard
        templates={templates}
        initialDraft={seed.draft}
        hasProfileData={seed.has_profile_data}
      />
    </div>
  );
}

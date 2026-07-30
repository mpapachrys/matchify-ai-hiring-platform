import { ProfileView } from "@/components/profile/profile-view";
import { PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import type { CandidateProfile } from "@/types/api";

export const metadata = { title: "Profile" };

export default async function CandidateProfilePage() {
  const profile = await serverFetch<CandidateProfile>("/candidates/me/profile");

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Your Profile"
        description="This is what hiring managers see when you apply. Build and edit it in the Resume Builder."
      />
      <ProfileView profile={profile} />
    </div>
  );
}

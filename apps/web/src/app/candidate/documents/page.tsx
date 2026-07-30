import { ResumePanel } from "@/components/documents/document-manager";
import { PageHeader } from "@/components/ui/misc";
import { serverFetch } from "@/lib/api/server";
import type { UserDocument } from "@/types/api";

export const metadata = { title: "Résumé" };

export default async function CandidateDocumentsPage() {
  const documents = await serverFetch<UserDocument[]>("/documents/me");
  // The résumé is the only document this platform keeps for a candidate, and it
  // is produced in the Resume Builder — so this page only ever shows résumés.
  const resumes = documents.filter((doc) => doc.type === "resume");

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Your Résumé"
        description="Your résumé is created and edited in the Resume Builder. It is attached automatically when you apply."
      />
      <ResumePanel resumes={resumes} />
    </div>
  );
}

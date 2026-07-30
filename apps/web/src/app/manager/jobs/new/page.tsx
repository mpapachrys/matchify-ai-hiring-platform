import { JobForm } from "@/components/jobs/job-form";
import { PageHeader } from "@/components/ui/misc";

export const metadata = { title: "Post a job" };

export default function NewJobPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Post a Job"
        description="Publish immediately, or save a draft and come back to it."
      />
      <JobForm />
    </div>
  );
}

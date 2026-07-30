import { ArrowRight, Briefcase, KanbanSquare, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Button } from "@/components/ui/button";
import { getSession, homeFor } from "@/lib/auth/session";
import { serverFetchOrNull } from "@/lib/api/server";
import type { Organization } from "@/types/api";

const FEATURES = [
  {
    icon: Briefcase,
    title: "Post and manage roles",
    body: "Draft a job, publish it, and close it when the seat is filled — with the applicant history preserved.",
  },
  {
    icon: KanbanSquare,
    title: "Run the pipeline",
    body: "Move candidates from applied through screening, interview and offer on a board built for it.",
  },
  {
    icon: ShieldCheck,
    title: "Verified candidates",
    body: "Collect resumes and verification documents through short-lived, access-controlled links.",
  },
];

export default async function LandingPage() {
  const user = await getSession();
  if (user) redirect(homeFor(user.role));

  const org = await serverFetchOrNull<Pick<Organization, "name" | "description">>(
    "/organization/public",
  );

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6">
      <header className="flex h-20 items-center justify-between">
        <div className="flex items-center gap-2">
          <Image src="/logo-mark.png" alt="Matchify" width={36} height={36} className="size-9" priority />
          <span className="text-lg font-bold">
            <span className="text-foreground">Match</span>
            <span className="gradient-text">ify</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild variant="primary" size="sm">
            <Link href="/register">Get started</Link>
          </Button>
        </div>
      </header>

      <section className="flex flex-1 flex-col justify-center py-16">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
          {org?.name ?? "Matchify"} · Careers
        </p>
        <h1 className="max-w-3xl text-5xl font-black leading-tight tracking-tight sm:text-6xl">
          Hiring that stays <span className="gradient-text">in one place</span>.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted">
          {org?.description ??
            "Candidates apply and track their progress. Hiring managers post roles, review applicants, and move them through the pipeline."}
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild variant="primary" size="lg">
            <Link href="/register">
              Create an account <ArrowRight className="size-4" />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/login">I already have one</Link>
          </Button>
        </div>

        <div className="mt-16 grid gap-4 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="panel p-5">
              <div className="mb-3 grid size-10 place-items-center rounded-xl border border-primary/30 bg-primary/15 text-[#a78bfa]">
                <feature.icon className="size-5" />
              </div>
              <h2 className="text-sm font-semibold text-foreground">{feature.title}</h2>
              <p className="mt-1.5 text-sm text-muted">{feature.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

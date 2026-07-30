import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-6xl font-black gradient-text">404</p>
      <h1 className="text-xl font-bold text-foreground">We couldn&rsquo;t find that page</h1>
      <p className="max-w-md text-sm text-muted">
        The job may have been closed, or you may not have access to it.
      </p>
      <Button asChild variant="primary">
        <Link href="/">Back to Matchify</Link>
      </Button>
    </div>
  );
}

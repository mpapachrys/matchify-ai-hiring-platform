import Image from "next/image";
import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 py-12">
      <Link href="/" className="mb-8 flex items-center gap-2">
        <Image src="/logo-mark.png" alt="Matchify" width={40} height={40} className="size-10" priority />
        <span className="text-xl font-bold">
          <span className="text-foreground">Match</span>
          <span className="gradient-text">ify</span>
        </span>
      </Link>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}

import type { Metadata } from "next";
import { Toaster } from "sonner";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Matchify — Hiring Platform",
    template: "%s · Matchify",
  },
  description:
    "Post roles, review applicants, and run your hiring pipeline in one place.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
        <Toaster
          theme="dark"
          position="top-right"
          toastOptions={{
            style: {
              background: "#1d1231",
              border: "1px solid #3f2c69",
              color: "#f4f1fb",
            },
          }}
        />
      </body>
    </html>
  );
}

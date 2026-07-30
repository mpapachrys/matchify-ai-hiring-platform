"use client";

import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";

const SENIORITY = ["intern", "junior", "mid", "senior", "lead", "principal"];
const WORK_MODES = ["onsite", "hybrid", "remote"];

/** Filters live in the URL so a filtered board is shareable and back/forward works. */
export function JobFilters() {
  const router = useRouter();
  const params = useSearchParams();
  const [search, setSearch] = React.useState(params.get("search") ?? "");

  function apply(next: Record<string, string>) {
    const query = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value) query.set(key, value);
      else query.delete(key);
    }
    query.delete("page");
    router.push(`?${query.toString()}`);
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        apply({ search });
      }}
      className="panel mb-5 flex flex-wrap items-end gap-3 p-4"
    >
      <div className="relative min-w-56 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by title, skill or keyword"
          className="pl-9"
          aria-label="Search jobs"
        />
      </div>

      <Select
        aria-label="Seniority"
        className="w-40"
        value={params.get("seniority") ?? ""}
        onChange={(event) => apply({ seniority: event.target.value })}
      >
        <option value="">Any seniority</option>
        {SENIORITY.map((level) => (
          <option key={level} value={level}>
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </option>
        ))}
      </Select>

      <Select
        aria-label="Work mode"
        className="w-40"
        value={params.get("work_mode") ?? ""}
        onChange={(event) => apply({ work_mode: event.target.value })}
      >
        <option value="">Any location</option>
        {WORK_MODES.map((mode) => (
          <option key={mode} value={mode}>
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </option>
        ))}
      </Select>

      <Button type="submit" variant="primary">
        Search
      </Button>
      {params.toString() ? (
        <Button type="button" variant="ghost" onClick={() => router.push("?")}>
          Clear
        </Button>
      ) : null}
    </form>
  );
}

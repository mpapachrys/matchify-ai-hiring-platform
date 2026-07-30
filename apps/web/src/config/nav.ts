import {
  Briefcase,
  Building2,
  Calendar,
  FileCheck2,
  FilePlus2,
  FileText,
  KanbanSquare,
  LayoutDashboard,
  Search,
  Settings,
  User,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Role } from "@/types/api";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const CANDIDATE_NAV: NavItem[] = [
  { href: "/candidate/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/candidate/jobs", label: "Browse Jobs", icon: Search },
  { href: "/candidate/applications", label: "My Applications", icon: FileText },
  { href: "/candidate/interviews", label: "Interviews", icon: Calendar },
  { href: "/candidate/resume-builder", label: "Resume Builder", icon: FilePlus2 },
  { href: "/candidate/profile", label: "Profile", icon: User },
  { href: "/candidate/documents", label: "Documents", icon: FileCheck2 },
  { href: "/candidate/settings", label: "Settings", icon: Settings },
];

const MANAGER_NAV: NavItem[] = [
  { href: "/manager/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/manager/jobs", label: "Jobs", icon: Briefcase },
  { href: "/manager/applicants", label: "Applicants", icon: Users },
  { href: "/manager/pipeline", label: "Pipeline", icon: KanbanSquare },
  { href: "/manager/calendar", label: "Calendar", icon: Calendar },
  { href: "/manager/organization", label: "Organization", icon: Building2 },
  { href: "/manager/settings", label: "Settings", icon: Settings },
];

export function navFor(role: Role): NavItem[] {
  return role === "hiring_manager" ? MANAGER_NAV : CANDIDATE_NAV;
}

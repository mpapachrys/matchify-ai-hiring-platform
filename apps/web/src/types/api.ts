/**
 * Hand-written mirrors of the FastAPI response models.
 *
 * `make types` regenerates the full set into packages/api-types from the
 * OpenAPI schema — these are the trimmed shapes the UI actually consumes.
 */

export type Role = "candidate" | "hiring_manager";

export type JobStatus = "draft" | "published" | "paused" | "closed" | "archived";

export type PipelineStage =
  | "applied"
  | "screening"
  | "interview"
  | "offer"
  | "hired"
  | "rejected"
  | "withdrawn";

export type SeniorityLevel = "intern" | "junior" | "mid" | "senior" | "lead" | "principal";
export type DegreeLevel =
  | "High School"
  | "Certificate"
  | "Diploma"
  | "Bachelor"
  | "Master"
  | "PhD";
/** CEFR plus Native — closed vocabulary so the AI graph gets one node per level. */
export type LanguageProficiency = "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "Native";
export type WorkMode = "onsite" | "hybrid" | "remote";
export type EmploymentType =
  | "full_time"
  | "part_time"
  | "contract"
  | "internship"
  | "temporary";

export type DocumentType =
  | "resume"
  | "passport"
  | "degree"
  | "mark_sheet"
  | "certificate"
  | "reference_letter"
  | "other";

export type DocumentStatus = "pending" | "verified" | "rejected";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  phone: string | null;
  avatar_url: string | null;
  is_admin: boolean;
  is_email_verified: boolean;
  created_at: string;
}

export interface Session {
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Salary {
  min: number | null;
  max: number | null;
  currency: string;
  period: string;
  is_public: boolean;
}

export interface JobLocation {
  country: string | null;
  city: string | null;
  is_remote: boolean;
}

/** Importance levels shown in the UI; the API stores the numeric weight. */
export const NICE_TO_HAVE_WEIGHTS = { nice: 0.3, important: 0.6, critical: 1.0 } as const;
export type ImportanceLevel = keyof typeof NICE_TO_HAVE_WEIGHTS;

export interface RequiredSkill {
  /** Stable slug — the same key the candidate export uses for skills. */
  slug: string;
  name: string;
  min_years: number | null;
}

export interface NiceToHaveSkill {
  slug: string;
  name: string;
  weight: number;
}

export interface RequiredEducation {
  degree_level: DegreeLevel | null;
  field_of_study: string | null;
}

export interface RequiredLanguage {
  language: string;
  min_proficiency: LanguageProficiency;
}

export interface MandatoryRequirements {
  min_years_total_experience: number | null;
  max_years_total_experience: number | null;
  education: RequiredEducation[];
  skills: RequiredSkill[];
  languages: RequiredLanguage[];
}

export interface NiceToHave {
  skills: NiceToHaveSkill[];
  certifications: string[];
  preferred_industries: string[];
}

export interface Job {
  id: string;
  title: string;
  slug: string;
  description: string;
  responsibilities: string[];
  mandatory: MandatoryRequirements;
  nice_to_have: NiceToHave;
  /** Derived flat slug list — for chips on cards, not for editing. */
  skills_required: string[];
  job_category: string | null;
  seniority: SeniorityLevel;
  employment_type: EmploymentType;
  work_mode: WorkMode;
  location: JobLocation;
  salary: Salary | null;
  openings: number;
  status: JobStatus;
  application_deadline: string | null;
  published_at: string | null;
  created_at: string;
  applications_count: number;
  has_applied: boolean;
  is_saved: boolean;
}

export interface JobStats {
  views: number;
  applications: number;
  shortlisted: number;
  hired: number;
}

export interface ManagerJob extends Job {
  created_by: string;
  can_edit: boolean;
  pipeline_stages: PipelineStage[];
  stats: JobStats;
  updated_at: string | null;
}

export interface JobSnapshot {
  title: string;
  location: string | null;
  employment_type: EmploymentType | null;
  seniority: SeniorityLevel | null;
}

export interface CandidateSnapshot {
  full_name: string;
  email: string;
  headline: string | null;
  avatar_url: string | null;
}

export type MatchStatus = "pending" | "scored" | "failed";

/** The AI team's confidence, with the factors behind it — manager-only. */
export interface Match {
  status: MatchStatus;
  confidence: number | null; // 0–1
  factors: Record<string, unknown>;
  graph_version: string | null;
  scored_at: string | null;
}

export type InterviewStatus = "none" | "awaiting_candidate" | "scheduled" | "cancelled";

/** Booked on the shared company Google Calendar via the calendar-mcp
 * assistant. Tracks separately from `stage` — a stage move doesn't imply a
 * booking, and cancelling a booking doesn't move the stage back. */
export interface Interview {
  status: InterviewStatus;
  event_id: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  html_link: string | null;
}

export interface CandidateApplication {
  id: string;
  job_id: string;
  job_snapshot: JobSnapshot;
  stage: PipelineStage;
  is_shortlisted: boolean;
  cover_letter: string | null;
  resume_id: string | null;
  applied_at: string;
  updated_at: string;
  withdrawn_at: string | null;
  timeline: { to_stage: PipelineStage; changed_at: string }[];
  match_status: MatchStatus;
  match_confidence: number | null; // 0–1, shown as a percentage
  interview: Interview;
}

export interface StageChange {
  from_stage: PipelineStage | null;
  to_stage: PipelineStage;
  changed_by: string | null;
  changed_at: string;
  note: string | null;
}

export interface InternalNote {
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
}

export interface ManagerApplication {
  id: string;
  job_id: string;
  candidate_id: string;
  job_snapshot: JobSnapshot;
  candidate_snapshot: CandidateSnapshot;
  stage: PipelineStage;
  stage_history: StageChange[];
  is_shortlisted: boolean;
  cover_letter: string | null;
  resume_id: string | null;
  answers: { question: string; answer: string }[];
  rating: number | null;
  notes: InternalNote[];
  match: Match;
  interview: Interview;
  applied_at: string;
  updated_at: string;
  withdrawn_at: string | null;
}

export interface InterviewSlot {
  start: string; // "HH:MM"
  end: string;
  available: boolean;
}

export interface AvailabilityOut {
  date: string; // "YYYY-MM-DD"
  slots: InterviewSlot[];
}

export interface InterviewActionOut {
  status: "scheduled" | "conflict" | "invalid_request";
  message: string;
}

/** One application approved for interview but not yet booked — what the
 * floating booking widget polls for to decide whether to show itself. */
export interface AwaitingInterviewItem {
  application_id: string;
  job_title: string;
}

/** One turn of the booking chat's transcript. `content` is always plain
 * text — a "user" turn is the label of whichever button was clicked. */
export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
}

/** A candidate-clickable next step. `id` encodes the action (e.g.
 * "pick_day:2026-08-04") — echoed back verbatim as `selected_action`. */
export interface AgentButton {
  id: string;
  label: string;
}

export interface AgentTurnOut {
  message: string;
  buttons: AgentButton[];
  done: boolean;
  history: AgentMessage[];
}

export interface Experience {
  company: string;
  title: string;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  location: string | null;
  description: string | null;
}

export interface Education {
  institution: string;
  degree: string;
  field: string | null;
  start_date: string | null;
  end_date: string | null;
  grade: string | null;
}

export interface CandidateProfile {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
  headline: string | null;
  summary: string | null;
  job_category: string | null;
  seniority: SeniorityLevel | null;
  location: {
    country: string | null;
    city: string | null;
    postal_code: string | null;
    address: string | null;
  };
  open_to_relocate: boolean;
  work_modes: WorkMode[];
  skills: string[];
  years_experience: number | null;
  expected_salary: {
    min: number | null;
    max: number | null;
    currency: string;
    period: string;
  } | null;
  experience: Experience[];
  education: Education[];
  languages: { name: string; level: string }[];
  links: { linkedin: string | null; github: string | null; portfolio: string | null };
  primary_resume_id: string | null;
  saved_job_ids: string[];
  completion_percent: number;
}

export type ParseStatus = "idle" | "queued" | "processing" | "done" | "failed";

export interface UserDocument {
  id: string;
  owner_id: string;
  type: DocumentType;
  status: DocumentStatus;
  filename: string;
  content_type: string;
  size_bytes: number;
  version: number;
  is_primary: boolean;
  is_generated: boolean;
  parse_status: ParseStatus;
  verification: {
    reviewed_by: string | null;
    reviewed_at: string | null;
    rejection_reason: string | null;
  };
  uploaded_at: string;
}

// ── resume builder ──────────────────────────────────────────────────────────

export interface ResumeTemplate {
  id: string;
  label: string;
  description: string;
}

export interface DraftExperience {
  company: string | null;
  title: string | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  location: string | null;
  description: string | null;
  /** Skills used in this role — required before a resume can be generated. */
  skills: string[];
  /** Employer's industry, from the platform's fixed list. */
  company_industry: string | null;
}

/** One thing blocking generation, addressed to a specific row. */
export interface DraftIssue {
  field: string;
  index: number | null;
  message: string;
}

export interface DraftEducation {
  institution: string | null;
  degree: string | null;
  degree_level: DegreeLevel | null;
  field: string | null;
  start_date: string | null;
  end_date: string | null;
  grade: string | null;
}

export interface DraftLanguage {
  name: string;
  level: LanguageProficiency | null;
}

export interface DraftCertification {
  name: string;
  issuer: string | null;
  issued_year: number | null;
  credential_id: string | null;
}

export interface DraftAchievements {
  career_highlights: string[];
  academic_distinctions: string[];
  awards_and_competitions: string[];
  projects_and_open_source: string[];
}

export interface DraftLinks {
  linkedin: string | null;
  github: string | null;
  portfolio: string | null;
}

export interface ResumeDraft {
  full_name: string;
  headline: string | null;
  email: string | null;
  phone: string | null;
  city: string | null;
  country: string | null;
  summary: string | null;
  // Not printed on the resume, but they drive matching and are shown to
  // managers — the builder owns them because nothing else can edit a profile.
  job_category: string | null;
  seniority: SeniorityLevel | null;
  open_to_relocate: boolean;
  work_modes: WorkMode[];
  // No flat `skills` and no `years_experience`: skills belong to the role that
  // used them, and years are derived from the date ranges.
  experience: DraftExperience[];
  education: DraftEducation[];
  languages: DraftLanguage[];
  certifications: DraftCertification[];
  achievements: DraftAchievements;
  links: DraftLinks;
}

export interface ResumeDraftSeed {
  draft: ResumeDraft;
  has_profile_data: boolean;
}

/** What the AI engine extracted from an uploaded CV — all fields optional. */
export interface ParsedResumeData {
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  headline?: string | null;
  summary?: string | null;
  job_category?: string | null;
  seniority?: string | null;
  location?: { country?: string | null; city?: string | null };
  skills?: string[];
  years_experience?: number | null;
  experience?: DraftExperience[];
  education?: DraftEducation[];
  languages?: DraftLanguage[];
  certifications?: DraftCertification[];
  achievements?: Partial<DraftAchievements>;
  links?: DraftLinks;
}

export interface ParseState {
  document_id: string;
  filename: string;
  status: ParseStatus;
  error: string | null;
  model_version: string | null;
  data: ParsedResumeData | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface GeneratedResume {
  document_id: string;
  filename: string;
  download_url: string;
  expires_in: number;
  is_primary: boolean;
}

export interface VerificationChecklist {
  required: DocumentType[];
  satisfied: DocumentType[];
  missing: DocumentType[];
  is_complete: boolean;
}

export interface TimePoint {
  date: string;
  value: number;
}

export interface StageCount {
  stage: string;
  count: number;
}

export interface CandidateAnalytics {
  jobs_applied: number;
  shortlisted: number;
  in_interview: number;
  offers: number;
  success_rate: number;
  profile_completion: number;
  applications_over_time: TimePoint[];
  success_rate_trend: { date: string; value: number }[];
  stage_breakdown: StageCount[];
}

export interface ManagerAnalytics {
  open_jobs: number;
  total_applications: number;
  shortlisted: number;
  hired: number;
  conversion_rate: number;
  applications_over_time: TimePoint[];
  funnel: StageCount[];
  top_jobs: {
    id: string;
    title: string;
    applications: number;
    shortlisted: number;
    status: string;
  }[];
}

export interface Organization {
  name: string;
  website: string | null;
  logo_url: string | null;
  description: string | null;
  industry: string | null;
  size: string | null;
  headquarters: {
    country: string | null;
    city: string | null;
    postal_code: string | null;
    address: string | null;
  };
  brand: { primary_color: string; accent_color: string };
  hiring: {
    default_pipeline_stages: PipelineStage[];
    require_cover_letter: boolean;
    required_documents: DocumentType[];
  };
}

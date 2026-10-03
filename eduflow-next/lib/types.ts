export type NodeType = "topic" | "subtopic" | "objective";
export type Origin = "official" | "teacher_defined" | "machine_extracted" | "machine_inferred";
export type EdgeType = "prerequisite" | "assessed_by" | "covered_by" | "part_of";
export type DocType = "textbook" | "past_paper" | "mark_scheme" | "syllabus" | "calendar";
export type MappingMethod = "embedding" | "lexical" | "llm" | "hybrid" | "human_corrected";
export type DayType = "school_day" | "non_teaching" | "exam_day";
export type ScheduledUnitStatus = "planned" | "taught" | "moved" | "compressed" | "removed";
export type MasteryStatus = "mastered" | "needs_reinforcement" | "reteach";
export type VerificationStatus = "verified" | "unsupported" | "partially_supported" | "not_checked";
export type PortalRole = "teacher" | "student" | "admin";

export interface PortalUser {
  id: string;
  name: string;
  email: string;
  role: PortalRole;
  enrollment_code?: string | null;
  created_at: string;
}

export interface ClassOutline {
  id: string;
  teacher_id: string;
  title: string;
  subject: string;
  content: string;
  source_text?: string | null;
  published: boolean;
  notes?: string | null;
  study_plan?: any;
  generated_by?: string | null;
  created_at: string;
}

export interface TeacherEnrollment {
  teacher_id: string;
  student_id: string;
}

export interface CurriculumNode {
  id: string;
  node_type: NodeType;
  label: string;
  description?: string | null;
  syllabus_ref?: string | null;
  origin: Origin;
  confidence: number;
  created_at: string;
}

export interface CurriculumEdge {
  id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: EdgeType;
  confidence: number;
}

export interface SourceDocument {
  id: string;
  title: string;
  doc_type: DocType;
  sha256: string;
  page_count: number;
  uri: string;
  created_at: string;
}

export interface SourceSpan {
  id: string;
  document_id: string;
  page_number: number;
  start_char: number;
  end_char: number;
  text_snippet: string;
}

export interface TeachingUnit {
  id: string;
  node_id: string;
  title: string;
  duration_minutes: number;
  order_index: number;
}

export interface ScheduledUnit {
  id: string;
  plan_version_id: string;
  unit_id: string;
  calendar_day_id: string;
  order_index: number;
  status: ScheduledUnitStatus;
  notes?: string | null;
}

export interface PlanVersion {
  id: string;
  name: string;
  version_number: number;
  is_active: boolean;
  created_at: string;
}

export interface AcademicCalendar {
  id: string;
  title: string;
  academic_year: string;
  start_date: string;
  end_date: string;
}

export interface CalendarDay {
  id: string;
  calendar_id: string;
  date: string;
  day_type: DayType;
  notes?: string | null;
}

export interface ExamQuestion {
  id: string;
  paper_id?: string | null;
  question_label: string;
  prompt_text: string;
  marks: number;
}

export interface QuestionNodeMapping {
  id: string;
  question_id: string;
  node_id: string;
  mapping_method: MappingMethod;
  confidence: number;
  verified_by_human: boolean;
}

export interface Claim {
  id: string;
  unit_id?: string | null;
  claim_text: string;
  verification_status: VerificationStatus;
  confidence: number;
  source_page?: number | null;
  created_at: string;
}

export interface ClaimEvidence {
  claim_id: string;
  source_span_id: string;
}

export interface ClassMasterySignal {
  id: string;
  node_id: string;
  class_group: string;
  mastery_percentage: number;
  status: MasteryStatus;
  recorded_at: string;
}

export interface TeacherCorrection {
  id: string;
  entity_type: string;
  entity_id: string;
  correction_data: any;
  comment?: string | null;
  applied_at: string;
}

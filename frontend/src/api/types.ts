export type Task = { id: string; name: string; mode: "review" | "direct"; status: string };
export type SourceSpan = { line_start: number; line_end: number; text: string };
export type PersonSegment = {
  id: string;
  name: string;
  line_start: number;
  line_end: number;
  content: string;
};
export type SegmentationResult = { people: PersonSegment[]; unassigned: SourceSpan[] };
export type TemplateSection = {
  id: string;
  name: string;
  method: string;
  confidence: number;
  required: boolean;
  locator: { part: string; paragraph_index: number; token: string | null };
  instruction: string;
  max_chars: number;
};

export type AnalysisProgress = {
  task_id: string;
  task_status: string;
  job_status: string | null;
  total_steps: number;
  succeeded_steps: number;
  current_step: string | null;
  failed_error_code: string | null;
  retryable: boolean;
};

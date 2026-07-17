import { api } from "./client";

export type ReviewSection = {
  section_key: string;
  name: string;
  revision: number;
  content: string;
  confirmed: boolean;
  editor: string;
  created_at: string | null;
  quality_status: string;
};

export type ReviewSource = {
  source_id: string;
  fact_id: string;
  person_id: string;
  person: string;
  line_start: number;
  line_end: number;
  excerpt: string;
};

export const reviewApi = {
  list: (taskId: string) => api<ReviewSection[]>(`/api/tasks/${taskId}/sections`),
  update: (taskId: string, sectionKey: string, content: string) => api<ReviewSection>(
    `/api/tasks/${taskId}/sections/${sectionKey}`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) },
  ),
  confirm: (taskId: string, sectionKey: string) => api<ReviewSection>(
    `/api/tasks/${taskId}/sections/${sectionKey}/confirm`, { method: "POST" },
  ),
  versions: (taskId: string, sectionKey: string) => api<ReviewSection[]>(
    `/api/tasks/${taskId}/sections/${sectionKey}/versions`,
  ),
  restore: (taskId: string, sectionKey: string, revision: number) => api<ReviewSection>(
    `/api/tasks/${taskId}/sections/${sectionKey}/restore/${revision}`, { method: "POST" },
  ),
  regenerate: (taskId: string, sectionKey: string, instruction: string) => api<ReviewSection>(
    `/api/tasks/${taskId}/sections/${sectionKey}/regenerate`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ instruction }) },
  ),
  sources: (taskId: string, sectionKey: string) => api<ReviewSource[]>(
    `/api/tasks/${taskId}/sections/${sectionKey}/sources`,
  ),
};

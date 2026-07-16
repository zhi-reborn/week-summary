import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api/client";
import type { AnalysisProgress } from "../api/types";
import { ErrorBanner } from "../components/error-banner";
import { ProgressStage } from "../components/progress-stage";
import { Stepper } from "../components/stepper";

const STAGES = [
  { prefix: "extract_person", title: "逐人提炼", description: "分别读取每位成员的内容，保留原文行号与引用。" },
  { prefix: "aggregate", title: "跨人员聚合", description: "归并同类工作，识别指标、日期和状态冲突。" },
  { prefix: "generate_section", title: "按模板成稿", description: "逐个生成模板板块，板块之间可独立恢复。" },
  { prefix: "quality_coverage", title: "质量与覆盖", description: "核对数字来源、人员覆盖和未引用事实。" },
] as const;

function stepLabel(step: string | null): string {
  if (!step) return "正在建立分析步骤";
  const [kind, entity] = step.split(":");
  if (kind === "extract_person") return `${entity} 周报提炼`;
  if (kind === "aggregate") return "跨人员内容聚合";
  if (kind === "generate_section") return `${entity} 板块生成`;
  if (kind === "quality_coverage") return "质量与覆盖检查";
  return step;
}

function stageState(progress: AnalysisProgress, prefix: string, index: number) {
  if (progress.task_status === "review" || progress.task_status === "completed") return "done" as const;
  const currentPrefix = progress.current_step?.split(":")[0];
  const currentIndex = STAGES.findIndex((stage) => stage.prefix === currentPrefix);
  if (currentIndex < 0) return "waiting" as const;
  if (index < currentIndex) return "done" as const;
  if (index > currentIndex) return "waiting" as const;
  return progress.task_status === "failed" ? "failed" as const : "active" as const;
}

export function AnalysisPage({ taskId }: { taskId: string }) {
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const timer = useRef<number | null>(null);

  const load = useCallback(async () => {
    let next = await api<AnalysisProgress>(`/api/tasks/${taskId}/analysis/status`);
    if (next.task_status === "ready_for_analysis") {
      next = await api<AnalysisProgress>(`/api/tasks/${taskId}/analysis/start`, { method: "POST" });
    }
    return next;
  }, [taskId]);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const next = await load();
        if (active) {
          setProgress(next);
          setError("");
          if (next.task_status === "analyzing") {
            timer.current = window.setTimeout(poll, document.hidden ? 10_000 : 2_000);
          }
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "读取分析进度失败");
      }
    };
    void poll();
    const reschedule = () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
      if (active && progress?.task_status === "analyzing") {
        timer.current = window.setTimeout(poll, document.hidden ? 10_000 : 2_000);
      }
    };
    document.addEventListener("visibilitychange", reschedule);
    return () => {
      active = false;
      if (timer.current !== null) window.clearTimeout(timer.current);
      document.removeEventListener("visibilitychange", reschedule);
    };
  }, [load, progress?.task_status]);

  async function retry() {
    try {
      const next = await api<AnalysisProgress>(`/api/tasks/${taskId}/analysis/retry`, { method: "POST" });
      setProgress(next);
      setNotice("分析任务已恢复");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重试失败");
    }
  }

  const failedLabel = progress?.task_status === "failed" ? `${stepLabel(progress.current_step)}失败` : "";
  const percentage = progress?.total_steps
    ? Math.round((progress.succeeded_steps / progress.total_steps) * 100)
    : 0;

  return (
    <main className="page-shell workflow-page analysis-page">
      <Stepper current={3} />
      <header className="analysis-heading">
        <div><p className="eyebrow">Step 04 / Analysis</p><h1>汇总正在成形</h1></div>
        <div className="analysis-score" aria-label={`分析进度 ${percentage}%`}><strong>{percentage}</strong><span>%</span></div>
      </header>
      {error ? <ErrorBanner message={error} /> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}
      {failedLabel ? (
        <section className="analysis-failure" aria-live="polite">
          <div><p className="eyebrow">Interrupted</p><h2>{failedLabel}</h2></div>
          <code>{progress?.failed_error_code}</code>
          <button className="primary-action" disabled={!progress?.retryable} onClick={retry} type="button">重试当前步骤</button>
        </section>
      ) : null}
      <section className="analysis-ledger" aria-live="polite">
        <div className="analysis-ledger__summary">
          <span>当前动作</span>
          <strong>{progress ? `${stepLabel(progress.current_step)}${progress.task_status === "analyzing" ? "…" : ""}` : "正在读取任务…"}</strong>
          <small>{progress ? `${progress.succeeded_steps} / ${progress.total_steps} 个持久化步骤已完成` : "连接本地任务队列"}</small>
        </div>
        <ol>
          {STAGES.map((stage, index) => (
            <ProgressStage
              key={stage.prefix}
              index={index + 1}
              title={stage.title}
              description={stage.description}
              state={progress ? stageState(progress, stage.prefix, index) : "waiting"}
            />
          ))}
        </ol>
      </section>
      {progress?.task_status === "review" ? <p className="analysis-ready">分析完成，内容已进入审核阶段。</p> : null}
    </main>
  );
}

export function AnalysisRoutePage() {
  const params = useParams();
  return <AnalysisPage taskId={params.id ?? ""} />;
}

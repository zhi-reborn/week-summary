import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { Task } from "../api/types";
import { ErrorBanner } from "../components/error-banner";
import { Stepper } from "../components/stepper";

export function UploadPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"review" | "direct">("review");
  const [reports, setReports] = useState<File | null>(null);
  const [template, setTemplate] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!reports || !template) return;
    setBusy(true);
    setError("");
    try {
      const task = await api<Task>("/api/tasks", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, mode }),
      });
      const data = new FormData();
      data.append("reports", reports);
      data.append("template", template);
      await api(`/api/tasks/${task.id}/inputs`, { method: "POST", body: data });
      await api(`/api/tasks/${task.id}/people/detect`, { method: "POST" });
      navigate(`/tasks/${task.id}/people`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page-shell workflow-page">
      <Stepper current={0} />
      <header><p className="eyebrow">Step 01 / Input</p><h1>提交本周材料</h1></header>
      {error ? <ErrorBanner message={error} /> : null}
      <form className="paper-form" onSubmit={submit}>
        <label>汇总名称<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：第 29 周团队周报" /></label>
        <fieldset className="mode-options">
          <legend>生成方式</legend>
          <label>
            <input type="radio" name="mode" value="review" checked={mode === "review"} onChange={() => setMode("review")} />
            <span><strong>校审后生成</strong><small>逐板块核对、修改并确认后生成 Word</small></span>
          </label>
          <label>
            <input type="radio" name="mode" value="direct" checked={mode === "direct"} onChange={() => setMode("direct")} />
            <span><strong>直接生成</strong><small>分析完成后自动生成 Word，可直接下载</small></span>
          </label>
        </fieldset>
        <label>合并周报 TXT<input required type="file" accept=".txt" onChange={(event) => setReports(event.target.files?.[0] ?? null)} /></label>
        <label>Word 模板 DOCX<input required type="file" accept=".docx" onChange={(event) => setTemplate(event.target.files?.[0] ?? null)} /></label>
        <button className="primary-action" disabled={busy || !reports || !template} type="submit">{busy ? "正在解析…" : "上传并识别人员"}</button>
      </form>
    </main>
  );
}

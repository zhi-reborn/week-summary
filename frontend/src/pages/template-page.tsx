import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { TemplateSection } from "../api/types";
import { ErrorBanner } from "../components/error-banner";
import { Stepper } from "../components/stepper";

export function TemplatePage({ taskId, onConfirmed }: { taskId: string; onConfirmed?: () => void }) {
  const [sections, setSections] = useState<TemplateSection[]>([]);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api<TemplateSection[]>(`/api/tasks/${taskId}/template/sections`).then((data) => {
      if (active) setSections(data);
    }).catch((reason: Error) => {
      if (active) setError(reason.message);
    });
    return () => { active = false; };
  }, [taskId]);

  const lowConfidence = sections.filter((section) => section.confidence < 0.85);
  const ready = sections.length > 0 && lowConfidence.every((section) => acknowledged.has(section.id));

  async function confirm() {
    try {
      await api(`/api/tasks/${taskId}/template/confirm`, { method: "POST" });
      onConfirmed?.();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认模板失败");
    }
  }

  return (
    <main className="page-shell workflow-page">
      <Stepper current={2} />
      <header><p className="eyebrow">Step 03 / Template</p><h1>确认模板板块</h1></header>
      {error ? <ErrorBanner message={error} /> : null}
      <section className="template-grid">
        {sections.map((section) => {
          const needsReview = section.confidence < 0.85;
          return (
            <article key={section.id}>
              <div><span className="record-id">{section.id}</span>{needsReview ? <strong className="review-flag">需要确认</strong> : <strong className="ok-flag">已识别</strong>}</div>
              <h2>{section.name}</h2>
              <p>{section.locator.part} · {section.method} · {Math.round(section.confidence * 100)}%</p>
              {needsReview ? <label className="check-row"><input type="checkbox" onChange={(event) => setAcknowledged((current) => { const next = new Set(current); event.target.checked ? next.add(section.id) : next.delete(section.id); return next; })} />我确认此板块定位正确</label> : null}
            </article>
          );
        })}
      </section>
      <button className="primary-action" disabled={!ready} onClick={confirm} type="button">确认模板板块</button>
    </main>
  );
}

export function TemplateRoutePage() {
  const params = useParams();
  const navigate = useNavigate();
  return <TemplatePage taskId={params.id ?? ""} onConfirmed={() => navigate(`/tasks/${params.id}/analysis`)} />;
}

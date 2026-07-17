import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { reviewApi, type ReviewSection, type ReviewSource } from "../api/review";
import { ErrorBanner } from "../components/error-banner";
import { RiskPanel } from "../features/review/risk-panel";
import { SectionEditor } from "../features/review/section-editor";
import { SectionNavigator } from "../features/review/section-navigator";
import { SourceDrawer } from "../features/review/source-drawer";
import { VersionHistory } from "../features/review/version-history";

export function ReviewPage({ taskId }: { taskId: string }) {
  const [sections, setSections] = useState<ReviewSection[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [draft, setDraft] = useState("");
  const [versions, setVersions] = useState<ReviewSection[]>([]);
  const [sources, setSources] = useState<ReviewSource[]>([]);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [undoRevisions, setUndoRevisions] = useState<Record<string, number>>({});
  const sourceButtonRef = useRef<HTMLButtonElement>(null);

  const selected = sections.find((section) => section.section_key === selectedKey) ?? null;

  useEffect(() => {
    let active = true;
    reviewApi.list(taskId).then((items) => {
      if (!active) return;
      setSections(items);
      if (items[0]) {
        setSelectedKey(items[0].section_key);
        setDraft(items[0].content);
        void reviewApi.versions(taskId, items[0].section_key).then((history) => {
          if (active) setVersions(history);
        }).catch((reason: Error) => {
          if (active) setError(reason.message);
        });
      }
    }).catch((reason: Error) => {
      if (active) setError(reason.message);
    });
    return () => { active = false; };
  }, [taskId]);

  function selectSection(section: ReviewSection) {
    setSelectedKey(section.section_key);
    setDraft(section.content);
    setNotice("");
    setError("");
    void reviewApi.versions(taskId, section.section_key).then(setVersions).catch((reason: Error) => setError(reason.message));
  }

  function replaceSection(updated: ReviewSection) {
    setSections((current) => current.map((item) => item.section_key === updated.section_key ? updated : item));
    setDraft(updated.content);
    void reviewApi.versions(taskId, updated.section_key).then(setVersions).catch((reason: Error) => setError(reason.message));
  }

  async function save() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const updated = await reviewApi.update(taskId, selected.section_key, draft);
      replaceSection(updated);
      setNotice(`已保存为版本 ${updated.revision}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const updated = await reviewApi.confirm(taskId, selected.section_key);
      replaceSection(updated);
      setNotice(`版本 ${updated.revision} 已确认`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  async function showSources() {
    if (!selected) return;
    setError("");
    try {
      setSources(await reviewApi.sources(taskId, selected.section_key));
      setSourcesOpen(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "读取来源失败");
    }
  }

  async function restore(revision: number) {
    if (!selected || !window.confirm(`确认恢复版本 ${revision}？当前内容会作为历史保留。`)) return;
    setError("");
    try {
      const updated = await reviewApi.restore(taskId, selected.section_key, revision);
      replaceSection(updated);
      setNotice(`已恢复版本 ${revision}，保存为版本 ${updated.revision}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "恢复失败");
    }
  }

  async function regenerate(instruction: string) {
    if (!selected) return;
    const previousRevision = selected.revision;
    setBusy(true);
    setError("");
    try {
      const updated = await reviewApi.regenerate(taskId, selected.section_key, instruction);
      setUndoRevisions((current) => ({ ...current, [selected.section_key]: previousRevision }));
      replaceSection(updated);
      setNotice(`已重新生成 ${selected.name}，保存为版本 ${updated.revision}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重新生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function undoGeneration() {
    if (!selected) return;
    const revision = undoRevisions[selected.section_key];
    if (!revision) return;
    setBusy(true);
    setError("");
    try {
      const updated = await reviewApi.restore(taskId, selected.section_key, revision);
      replaceSection(updated);
      setUndoRevisions((current) => {
        const next = { ...current };
        delete next[selected.section_key];
        return next;
      });
      setNotice(`已撤销本次生成，保存为版本 ${updated.revision}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "撤销失败");
    } finally {
      setBusy(false);
    }
  }

  function closeSources() {
    setSourcesOpen(false);
    window.requestAnimationFrame(() => sourceButtonRef.current?.focus());
  }

  return (
    <main className="review-workspace">
      <header className="review-header">
        <div><p className="eyebrow">Review desk / Local draft</p><h1>周报校审台</h1></div>
        <p>{sections.filter((section) => section.confirmed).length} / {sections.length} 个板块已确认</p>
      </header>
      {error ? <div className="review-message"><ErrorBanner message={error} /></div> : null}
      {notice ? <p className="review-message success-banner">{notice}</p> : null}
      <div className="review-grid">
        <SectionNavigator sections={sections} selectedKey={selectedKey} onSelect={selectSection} />
        {selected ? (
          <SectionEditor
            section={selected}
            draft={draft}
            busy={busy}
            canUndo={Boolean(undoRevisions[selected.section_key])}
            onChange={setDraft}
            onSave={save}
            onConfirm={confirm}
            onRegenerate={regenerate}
            onUndo={undoGeneration}
          />
        ) : <section className="review-editor review-loading">正在装订校审稿…</section>}
        <aside className="review-sidebar">
          {selected ? <>
            <RiskPanel qualityStatus={selected.quality_status} sourceButtonRef={sourceButtonRef} onShowSources={showSources} />
            <VersionHistory versions={versions} currentRevision={selected.revision} onRestore={restore} />
          </> : null}
        </aside>
      </div>
      <SourceDrawer open={sourcesOpen} sources={sources} onClose={closeSources} />
    </main>
  );
}

export function ReviewRoutePage() {
  const params = useParams();
  return <ReviewPage taskId={params.id ?? ""} />;
}

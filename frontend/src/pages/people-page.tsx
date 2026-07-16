import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { PersonSegment, SegmentationResult, SourceSpan } from "../api/types";
import { ErrorBanner } from "../components/error-banner";
import { Stepper } from "../components/stepper";

export function PeopleRoutePage() {
  const params = useParams();
  const navigate = useNavigate();
  return <PeoplePage taskId={params.id ?? ""} onConfirmed={() => navigate(`/tasks/${params.id}/template`)} />;
}

function withStableIds(people: PersonSegment[]): PersonSegment[] {
  return people.map((person, index) => ({ ...person, id: `P${String(index + 1).padStart(2, "0")}` }));
}

function validate(result: SegmentationResult): string {
  const names = result.people.map((person) => person.name.trim());
  if (names.some((name) => !name)) return "人员姓名不能为空";
  if (new Set(names).size !== names.length) return "人员姓名不能重复";
  const ranges = [...result.people, ...result.unassigned].sort((left, right) => left.line_start - right.line_start);
  if (ranges.some((range) => range.line_start > range.line_end)) return "起始行不能大于结束行";
  if (ranges.some((range, index) => index > 0 && ranges[index - 1].line_end >= range.line_start)) return "文本行范围不能重叠";
  return "";
}

export function PeoplePage({ taskId, onConfirmed }: { taskId: string; onConfirmed?: () => void }) {
  const [result, setResult] = useState<SegmentationResult | null>(null);
  const [splitLines, setSplitLines] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api<SegmentationResult>(`/api/tasks/${taskId}/people`).then((data) => {
      if (active) setResult(data);
    }).catch((reason: Error) => {
      if (active) setError(reason.message);
    });
    return () => { active = false; };
  }, [taskId]);

  function replacePerson(index: number, patch: Partial<PersonSegment>) {
    if (!result) return;
    const people = result.people.map((person, position) => position === index ? { ...person, ...patch } : person);
    setResult({ ...result, people });
    setDirty(true);
    setError("");
  }

  function deletePerson(index: number) {
    if (!result) return;
    const person = result.people[index];
    const removed: SourceSpan = { line_start: person.line_start, line_end: person.line_end, text: person.content };
    setResult({ people: withStableIds(result.people.filter((_, position) => position !== index)), unassigned: [...result.unassigned, removed] });
    setDirty(true);
  }

  function addFromUnassigned() {
    if (!result?.unassigned.length) {
      setError("没有可补录的未分配文本，请先拆分现有人员范围");
      return;
    }
    const [source, ...unassigned] = result.unassigned;
    const people = withStableIds([...result.people, {
      id: "",
      name: `待命名${result.people.length + 1}`,
      line_start: source.line_start,
      line_end: source.line_end,
      content: source.text,
    }]).sort((left, right) => left.line_start - right.line_start);
    setResult({ people: withStableIds(people), unassigned });
    setDirty(true);
    setError("");
  }

  function mergeNext(index: number) {
    if (!result || index >= result.people.length - 1) return;
    const current = result.people[index];
    const next = result.people[index + 1];
    const merged: PersonSegment = {
      ...current,
      line_end: next.line_end,
      content: [current.content, next.content].filter(Boolean).join("\n"),
    };
    const people = [...result.people.slice(0, index), merged, ...result.people.slice(index + 2)];
    setResult({ ...result, people: withStableIds(people) });
    setDirty(true);
    setError("");
  }

  function splitPerson(index: number) {
    if (!result) return;
    const person = result.people[index];
    const splitAt = Number(splitLines[person.id]);
    if (!Number.isInteger(splitAt) || splitAt <= person.line_start || splitAt > person.line_end) {
      setError(`拆分行号必须在 ${person.line_start + 1}–${person.line_end} 之间`);
      return;
    }
    const contentLines = person.content.split("\n");
    const contentOffset = Math.max(0, splitAt - person.line_start - 1);
    const first = { ...person, line_end: splitAt - 1, content: contentLines.slice(0, contentOffset).join("\n") };
    const second = {
      ...person,
      id: "",
      name: `${person.name}-2`,
      line_start: splitAt,
      content: contentLines.slice(contentOffset).join("\n"),
    };
    const people = [...result.people.slice(0, index), first, second, ...result.people.slice(index + 1)];
    setResult({ ...result, people: withStableIds(people) });
    setDirty(true);
    setError("");
  }

  async function save(): Promise<boolean> {
    if (!result) return false;
    const validationError = validate(result);
    if (validationError) {
      setError(validationError);
      return false;
    }
    setSaving(true);
    setError("");
    try {
      const saved = await api<SegmentationResult>(`/api/tasks/${taskId}/people`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result),
      });
      setResult(saved);
      setDirty(false);
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    if (dirty && !(await save())) return;
    try {
      await api(`/api/tasks/${taskId}/people/confirm`, { method: "POST" });
      await api(`/api/tasks/${taskId}/template/detect`, { method: "POST" });
      onConfirmed?.();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认失败");
    }
  }

  return (
    <main className="page-shell workflow-page">
      <Stepper current={1} />
      <header><p className="eyebrow">Step 02 / People</p><h1>核对人员边界</h1></header>
      {error ? <ErrorBanner message={error} /> : null}
      {result?.unassigned.length ? <ErrorBanner message="存在未分配内容" /> : null}
      <div className="editor-toolbar">
        <p>{result ? `已识别 ${result.people.length} 人` : "正在读取识别结果…"}</p>
        <button className="text-action" onClick={addFromUnassigned} type="button">从未分配文本补录人员</button>
      </div>
      <section className="record-list">
        {result?.people.map((person, index) => (
          <article key={person.id}>
            <span className="record-id">{person.id}</span>
            <div className="person-fields">
              <label>姓名<input aria-label={`${person.id} 姓名`} value={person.name} onChange={(event) => replacePerson(index, { name: event.target.value })} /></label>
              <label>起始行<input aria-label={`${person.id} 起始行`} min="1" type="number" value={person.line_start} onChange={(event) => replacePerson(index, { line_start: Number(event.target.value) })} /></label>
              <label>结束行<input aria-label={`${person.id} 结束行`} min="1" type="number" value={person.line_end} onChange={(event) => replacePerson(index, { line_end: Number(event.target.value) })} /></label>
            </div>
            <label className="content-field">原文内容<textarea aria-label={`${person.id} 原文内容`} rows={4} value={person.content} onChange={(event) => replacePerson(index, { content: event.target.value })} /></label>
            <div className="record-actions">
              <label>从第 <input aria-label={`${person.id} 拆分行号`} min={person.line_start + 1} max={person.line_end} type="number" value={splitLines[person.id] ?? ""} onChange={(event) => setSplitLines({ ...splitLines, [person.id]: event.target.value })} /> 行拆分</label>
              <button aria-label={`拆分 ${person.id}`} className="text-action" onClick={() => splitPerson(index)} type="button">拆分</button>
              {index < result.people.length - 1 ? <button aria-label={`合并 ${person.id} 与下一段`} className="text-action" onClick={() => mergeNext(index)} type="button">合并下一段</button> : null}
              <button aria-label={`删除 ${person.id}`} className="danger-action" onClick={() => deletePerson(index)} type="button">删除</button>
            </div>
          </article>
        ))}
      </section>
      <div className="footer-actions">
        <button className="text-action save-action" disabled={!dirty || saving} onClick={() => { void save(); }} type="button">{saving ? "正在保存…" : "保存修正"}</button>
        <button className="primary-action" disabled={!result || result.people.length === 0 || result.unassigned.length > 0 || saving} onClick={() => { void confirm(); }} type="button">确认人员拆分</button>
      </div>
    </main>
  );
}

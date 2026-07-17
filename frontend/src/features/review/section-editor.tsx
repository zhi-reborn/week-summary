import type { ReviewSection } from "../../api/review";
import { useEffect, useState } from "react";

export function SectionEditor({
  section,
  draft,
  busy,
  canUndo,
  onChange,
  onSave,
  onConfirm,
  onRegenerate,
  onUndo,
}: {
  section: ReviewSection;
  draft: string;
  busy: boolean;
  canUndo: boolean;
  onChange: (content: string) => void;
  onSave: () => void;
  onConfirm: () => void;
  onRegenerate: (instruction: string) => void;
  onUndo: () => void;
}) {
  const [instruction, setInstruction] = useState("");
  const changed = draft !== section.content;
  useEffect(() => setInstruction(""), [section.section_key]);
  return (
    <section className="review-editor" aria-labelledby="review-section-title">
      <div className="review-editor__heading">
        <div>
          <p className="review-column-label">Section draft / v{section.revision}</p>
          <h2 id="review-section-title">{section.name}</h2>
        </div>
        <span className={`review-state review-state--${section.confirmed ? "confirmed" : "draft"}`}>
          {section.confirmed ? "已确认" : "待校审"}
        </span>
      </div>
      <label className="review-textarea">
        <span>板块内容</span>
        <textarea
          aria-label="板块内容"
          onChange={(event) => onChange(event.target.value)}
          rows={16}
          value={draft}
        />
      </label>
      <div className="review-editor__meta">
        <span>{draft.length} 字</span>
        <span>{changed ? "有未保存修改" : "内容已保存"}</span>
      </div>
      <section className="regenerate-box" aria-labelledby="regenerate-title">
        <div>
          <p className="review-column-label">Focused rewrite</p>
          <h3 id="regenerate-title">只重新生成当前板块</h3>
        </div>
        <label>
          <span>重新生成要求</span>
          <textarea
            aria-label="重新生成要求"
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="例如：突出阻塞原因，控制在三条以内"
            rows={2}
            value={instruction}
          />
        </label>
        <div>
          {canUndo ? <button className="text-action" disabled={busy} onClick={onUndo} type="button">撤销本次生成</button> : <span />}
          <button className="text-action" disabled={busy || changed} onClick={() => onRegenerate(instruction)} type="button">
            {busy ? "模型处理中…" : "重新生成本板块"}
          </button>
        </div>
      </section>
      <div className="review-editor__actions">
        <button className="text-action" disabled={busy || !changed || !draft.trim()} onClick={onSave} type="button">
          保存修改
        </button>
        <button className="primary-action" disabled={busy || changed || section.confirmed} onClick={onConfirm} type="button">
          确认本板块
        </button>
      </div>
    </section>
  );
}

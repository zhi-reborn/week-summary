import type { ReviewSection } from "../../api/review";

export function SectionEditor({
  section,
  draft,
  busy,
  onChange,
  onSave,
  onConfirm,
}: {
  section: ReviewSection;
  draft: string;
  busy: boolean;
  onChange: (content: string) => void;
  onSave: () => void;
  onConfirm: () => void;
}) {
  const changed = draft !== section.content;
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

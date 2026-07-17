import type { ReviewSource } from "../../api/review";

export function SourceDrawer({
  open,
  sources,
  onClose,
}: {
  open: boolean;
  sources: ReviewSource[];
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <aside className="source-drawer" role="dialog" aria-modal="true" aria-labelledby="source-drawer-title">
      <div className="source-drawer__heading">
        <div><p className="review-column-label">Source ledger</p><h2 id="source-drawer-title">原文来源</h2></div>
        <button autoFocus aria-label="关闭来源" className="text-action" onClick={onClose} type="button">关闭</button>
      </div>
      {sources.length ? (
        <ol>
          {sources.map((source) => (
            <li key={source.source_id}>
              <strong>{source.person} · 原文第 {source.line_start}{source.line_end === source.line_start ? "" : `–${source.line_end}`} 行</strong>
              <blockquote>{source.excerpt}</blockquote>
              <small>{source.fact_id} / {source.source_id}</small>
            </li>
          ))}
        </ol>
      ) : <p className="empty-note">本板块没有可展示的来源。</p>}
    </aside>
  );
}

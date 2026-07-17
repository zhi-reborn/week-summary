import type { ReviewSection } from "../../api/review";

export function VersionHistory({
  versions,
  currentRevision,
  onRestore,
}: {
  versions: ReviewSection[];
  currentRevision: number;
  onRestore: (revision: number) => void;
}) {
  return (
    <section className="review-side-section version-history" aria-labelledby="version-title">
      <p className="review-column-label">Revision archive</p>
      <h2 id="version-title">版本历史</h2>
      <ol>
        {versions.map((version) => (
          <li key={version.revision}>
            <div><strong>版本 {version.revision}</strong><small>{version.confirmed ? "确认版本" : version.editor}</small></div>
            {version.revision === currentRevision ? <span>当前</span> : (
              <button aria-label={`恢复版本 ${version.revision}`} className="text-action" onClick={() => onRestore(version.revision)} type="button">恢复</button>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

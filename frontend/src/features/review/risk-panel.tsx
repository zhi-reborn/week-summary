import type { RefObject } from "react";

const QUALITY_LABELS: Record<string, string> = {
  pass: "来源检查通过",
  confirm: "建议人工确认",
  risk: "存在来源风险",
  failed: "未通过质量检查",
};

export function RiskPanel({
  qualityStatus,
  sourceButtonRef,
  onShowSources,
}: {
  qualityStatus: string;
  sourceButtonRef: RefObject<HTMLButtonElement>;
  onShowSources: () => void;
}) {
  return (
    <section className="review-side-section" aria-labelledby="quality-title">
      <p className="review-column-label">Quality signal</p>
      <h2 id="quality-title">质量提示</h2>
      <div className={`quality-ticket quality-ticket--${qualityStatus}`}>
        <span>{qualityStatus.toUpperCase()}</span>
        <strong>{QUALITY_LABELS[qualityStatus] ?? "等待质量检查"}</strong>
      </div>
      <button ref={sourceButtonRef} className="text-action review-source-action" onClick={onShowSources} type="button">
        查看来源
      </button>
    </section>
  );
}

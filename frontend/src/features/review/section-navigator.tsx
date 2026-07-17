import type { ReviewSection } from "../../api/review";

export function SectionNavigator({
  sections,
  selectedKey,
  onSelect,
}: {
  sections: ReviewSection[];
  selectedKey: string;
  onSelect: (section: ReviewSection) => void;
}) {
  return (
    <nav className="review-nav" aria-label="模板板块">
      <p className="review-column-label">Document map</p>
      <ol>
        {sections.map((section, index) => (
          <li key={section.section_key}>
            <button
              aria-current={selectedKey === section.section_key ? "page" : undefined}
              className={selectedKey === section.section_key ? "is-selected" : ""}
              onClick={() => onSelect(section)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{section.name}</strong>
              <small>{section.confirmed ? "已确认" : `版本 ${section.revision}`}</small>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

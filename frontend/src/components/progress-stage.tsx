type StageState = "waiting" | "active" | "failed" | "done";

const LABELS: Record<StageState, string> = {
  waiting: "等待",
  active: "进行中",
  failed: "需处理",
  done: "完成",
};

export function ProgressStage({
  index,
  title,
  description,
  state,
}: {
  index: number;
  title: string;
  description: string;
  state: StageState;
}) {
  return (
    <li className={`progress-stage progress-stage--${state}`}>
      <span className="progress-stage__number">{String(index).padStart(2, "0")}</span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <strong>{LABELS[state]}</strong>
    </li>
  );
}

const STEPS = ["上传材料", "确认人员", "确认模板", "开始分析"];

export function Stepper({ current }: { current: number }) {
  return (
    <ol className="stepper" aria-label="汇总步骤">
      {STEPS.map((step, index) => (
        <li className={index <= current ? "is-active" : ""} key={step}>
          <span>{String(index + 1).padStart(2, "0")}</span>{step}
        </li>
      ))}
    </ol>
  );
}


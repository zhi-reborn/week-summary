import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SectionEditor } from "../features/review/section-editor";

const section = {
  section_key: "risk",
  name: "风险问题",
  required: true,
  revision: 2,
  content: "资源存在风险",
  confirmed: false,
  editor: "local-user",
  created_at: null,
  quality_status: "risk",
};

describe("SectionEditor", () => {
  it("submits one-section regeneration instructions and supports undo", () => {
    const regenerate = vi.fn();
    const undo = vi.fn();
    render(
      <SectionEditor
        section={section}
        draft={section.content}
        busy={false}
        canUndo
        onChange={vi.fn()}
        onSave={vi.fn()}
        onConfirm={vi.fn()}
        onRegenerate={regenerate}
        onUndo={undo}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "重新生成要求" }), {
      target: { value: "突出阻塞原因，控制在三条以内" },
    });
    fireEvent.click(screen.getByRole("button", { name: "重新生成本板块" }));
    fireEvent.click(screen.getByRole("button", { name: "撤销本次生成" }));

    expect(regenerate).toHaveBeenCalledWith("突出阻塞原因，控制在三条以内");
    expect(undo).toHaveBeenCalledOnce();
  });
});

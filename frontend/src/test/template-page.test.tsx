import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TemplatePage } from "../pages/template-page";

describe("TemplatePage", () => {
  it("requires explicit confirmation for low-confidence sections", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ([{
        id: "S01",
        name: "风险问题",
        method: "heading_text",
        confidence: 0.8,
        required: true,
        locator: { part: "document", paragraph_index: 2, token: null },
        instruction: "",
        max_chars: 1200,
      }]),
    }));

    render(<TemplatePage taskId="task-1" />);

    expect(await screen.findByText("需要确认")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认模板板块" })).toBeDisabled();
  });

  it("explains when no template positions were recognized", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }));

    render(<TemplatePage taskId="task-1" />);

    expect(await screen.findByText(/模板中没有可识别的填写位置/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认模板板块" })).toBeDisabled();
  });
});

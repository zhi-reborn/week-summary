import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReviewPage } from "../pages/review-page";

const section = {
  section_key: "progress",
  name: "本周进展",
  revision: 1,
  content: "张三完成项目 A",
  required: true,
  confirmed: false,
  editor: "local-user",
  created_at: "2026-07-16T08:00:00Z",
  quality_status: "pass",
};

function response(payload: unknown, ok = true) {
  return { ok, json: async () => payload };
}

describe("ReviewPage", () => {
  it("edits a section and shows its source excerpt", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/sources")) {
        return Promise.resolve(response([{
          source_id: "F01:S1",
          fact_id: "F01",
          person_id: "P01",
          person: "张三",
          line_start: 2,
          line_end: 2,
          excerpt: "完成项目 A",
        }]));
      }
      if (path.endsWith("/versions")) return Promise.resolve(response([section]));
      if (init?.method === "PUT") {
        return Promise.resolve(response({ ...section, revision: 2, content: "人工调整内容" }));
      }
      return Promise.resolve(response([section]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewPage taskId="task-1" />);

    fireEvent.click(await screen.findByRole("button", { name: /本周进展/ }));
    const editor = screen.getByRole("textbox", { name: "板块内容" });
    fireEvent.change(editor, { target: { value: "人工调整内容" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
    expect(await screen.findByText("已保存为版本 2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看来源" }));
    expect(await screen.findByText("张三 · 原文第 2 行")).toBeInTheDocument();
    expect(screen.getByText("完成项目 A")).toBeInTheDocument();
  });

  it("keeps unsaved text when saving fails", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/versions")) return Promise.resolve(response([section]));
      if (init?.method === "PUT") {
        return Promise.resolve(response({ code: "SAVE_FAILED", message: "保存失败" }, false));
      }
      return Promise.resolve(response([section]));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewPage taskId="task-1" />);
    const editor = await screen.findByRole("textbox", { name: "板块内容" });

    fireEvent.change(editor, { target: { value: "尚未保存的人工内容" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    expect(await screen.findByText("保存失败")).toBeInTheDocument();
    await waitFor(() => expect(editor).toHaveValue("尚未保存的人工内容"));
  });

  it("exports after every section is confirmed", async () => {
    const confirmed = { ...section, confirmed: true };
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/versions")) return Promise.resolve(response([confirmed]));
      if (path.endsWith("/export") && init?.method === "POST") {
        return Promise.resolve(response({ status: "completed", download_name: "周报汇总.docx" }));
      }
      return Promise.resolve(response([confirmed]));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewPage taskId="task-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "生成并下载 Word" }));

    expect(await screen.findByRole("link", { name: "下载周报汇总.docx" })).toHaveAttribute(
      "href",
      "/api/tasks/task-1/download",
    );
  });

  it("confirms all sections in one click", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/versions")) return Promise.resolve(response([section]));
      if (path.endsWith("/batch-confirm") && init?.method === "POST") {
        return Promise.resolve(response([{ ...section, confirmed: true, revision: 2 }]));
      }
      return Promise.resolve(response([section]));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewPage taskId="task-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "一键确认所有板块" }));

    expect(await screen.findByText("已一键确认 1 个板块")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/batch-confirm"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("allows export when only optional sections are unconfirmed", async () => {
    const optional = { ...section, required: false };
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/versions")) return Promise.resolve(response([optional]));
      if (path.endsWith("/export") && init?.method === "POST") {
        return Promise.resolve(response({ status: "completed", download_name: "周报汇总.docx" }));
      }
      return Promise.resolve(response([optional]));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewPage taskId="task-1" />);

    const button = await screen.findByRole("button", { name: "生成并下载 Word" });
    expect(button).toBeEnabled();
  });
});

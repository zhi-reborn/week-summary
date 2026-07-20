import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { UploadPage } from "../pages/upload-page";

function response(payload: unknown) {
  return { ok: true, json: async () => payload };
}

describe("UploadPage", () => {
  it("submits the selected direct generation mode", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string) => {
      if (path === "/api/tasks") {
        return Promise.resolve(response({ id: "task-1", name: "第29周", mode: "direct", status: "draft" }));
      }
      return Promise.resolve(response({}));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<BrowserRouter><UploadPage /></BrowserRouter>);

    fireEvent.change(screen.getByLabelText("汇总名称"), { target: { value: "第29周" } });
    fireEvent.click(screen.getByRole("radio", { name: /直接生成/ }));
    fireEvent.change(screen.getByLabelText("合并周报 TXT"), {
      target: { files: [new File(["张三\n完成A"], "reports.txt", { type: "text/plain" })] },
    });
    fireEvent.change(screen.getByLabelText("Word 模板 DOCX"), {
      target: { files: [new File(["docx"], "template.docx")] },
    });
    const submit = screen.getByRole("button", { name: "上传并识别人员" });
    fireEvent.submit(submit.closest("form")!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks",
      expect.objectContaining({ body: JSON.stringify({ name: "第29周", mode: "direct" }) }),
    ));
  });
});

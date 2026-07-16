import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PeoplePage } from "../pages/people-page";

describe("PeoplePage", () => {
  it("blocks confirmation while text remains unassigned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        people: [{ id: "P01", name: "张三", line_start: 1, line_end: 2, content: "完成A" }],
        unassigned: [{ line_start: 3, line_end: 3, text: "未知内容" }],
      }),
    }));

    render(<PeoplePage taskId="task-1" />);

    expect(await screen.findByText("存在未分配内容")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认人员拆分" })).toBeDisabled();
  });

  it("renames, splits, and saves the complete people list", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          people: [{ id: "P01", name: "张三", line_start: 1, line_end: 3, content: "完成A\n计划B" }],
          unassigned: [],
        }),
      })
      .mockImplementationOnce(async (_path: string, init?: RequestInit) => ({
        ok: true,
        json: async () => JSON.parse(String(init?.body)),
      }));
    vi.stubGlobal("fetch", fetchMock);

    render(<PeoplePage taskId="task-1" />);

    fireEvent.change(await screen.findByLabelText("P01 姓名"), { target: { value: "张三丰" } });
    fireEvent.change(screen.getByLabelText("P01 拆分行号"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "拆分 P01" }));
    fireEvent.click(screen.getByRole("button", { name: "保存修正" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [, request] = fetchMock.mock.calls[1];
    expect(request.method).toBe("PUT");
    expect(JSON.parse(request.body)).toMatchObject({
      people: [
        { id: "P01", name: "张三丰", line_start: 1, line_end: 2, content: "完成A" },
        { id: "P02", name: "张三丰-2", line_start: 3, line_end: 3, content: "计划B" },
      ],
      unassigned: [],
    });
  });
});

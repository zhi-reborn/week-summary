import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnalysisPage } from "../pages/analysis-page";

const failedProgress = {
  task_id: "task-1",
  task_status: "failed",
  job_status: "failed",
  total_steps: 6,
  succeeded_steps: 2,
  current_step: "extract_person:P02",
  failed_error_code: "MODEL_TIMEOUT",
  retryable: true,
  quality_findings: [],
};

function response(payload: unknown) {
  return { ok: true, json: async () => payload };
}

describe("AnalysisPage", () => {
  it("shows the failed step and retries only the failed analysis", async () => {
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/retry") && init?.method === "POST") {
        return Promise.resolve(response({
          ...failedProgress,
          task_status: "analyzing",
          job_status: "queued",
          retryable: false,
        }));
      }
      return Promise.resolve(response(failedProgress));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AnalysisPage taskId="task-1" />);

    expect(await screen.findByText("P02 周报提炼失败")).toBeInTheDocument();
    expect(screen.getByText("MODEL_TIMEOUT")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试当前步骤" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks/task-1/analysis/retry",
      { method: "POST" },
    ));
    expect(await screen.findByText("分析任务已恢复")).toBeInTheDocument();
  });

  it("starts a confirmed task when opening the page", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({
        ...failedProgress,
        task_status: "ready_for_analysis",
        job_status: null,
        total_steps: 0,
        succeeded_steps: 0,
        current_step: null,
        failed_error_code: null,
        retryable: false,
      }))
      .mockResolvedValueOnce(response({
        ...failedProgress,
        task_status: "analyzing",
        job_status: "queued",
        total_steps: 0,
        succeeded_steps: 0,
        current_step: null,
        failed_error_code: null,
        retryable: false,
      }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AnalysisPage taskId="task-1" />);

    expect(await screen.findByText("正在建立分析步骤…")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/tasks/task-1/analysis/start",
      { method: "POST" },
    );
  });

  it("offers the generated document when direct mode completes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ...failedProgress,
      task_status: "completed",
      job_status: "succeeded",
      total_steps: 4,
      succeeded_steps: 4,
      current_step: null,
      failed_error_code: null,
      retryable: false,
      quality_findings: [{
        code: "UNSOURCED_NUMBER",
        message: "数字、日期或版本缺少来源：95%",
        token: "95%",
      }],
    })));

    render(<AnalysisPage taskId="task-1" />);

    expect(await screen.findByRole("link", { name: "下载汇总 Word" })).toHaveAttribute(
      "href",
      "/api/tasks/task-1/download",
    );
    expect(screen.getByRole("heading", { name: "质量提示" })).toBeInTheDocument();
    expect(screen.getByText("数字、日期或版本缺少来源：95%")).toBeInTheDocument();
  });

  it("retries a failed direct export without repeating analysis", async () => {
    const exportFailed = {
      ...failedProgress,
      task_status: "export_failed",
      current_step: null,
      failed_error_code: "DOCX_VALIDATION_FAILED",
      retryable: false,
    };
    let current = exportFailed;
    const fetchMock = vi.fn().mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/export") && init?.method === "POST") {
        current = { ...exportFailed, task_status: "completed" };
        return Promise.resolve(response({ status: "completed", download_name: "周报汇总.docx" }));
      }
      return Promise.resolve(response(current));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AnalysisPage taskId="task-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "重试生成 Word" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks/task-1/export",
      { method: "POST" },
    ));
    expect(await screen.findByRole("link", { name: "下载汇总 Word" })).toBeInTheDocument();
  });
});

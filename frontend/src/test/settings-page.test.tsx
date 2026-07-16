import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { SettingsPage } from "../pages/settings-page";


describe("SettingsPage", () => {
  it("keeps the saved API key masked and tests the private model", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          base_url: "http://127.0.0.1:8000/v1",
          model: "private-model",
          timeout_seconds: 120,
          max_retries: 2,
          temperature: 0.1,
          context_tokens: 8192,
          has_api_key: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ reachable: true, model_callable: true, json_mode: true, message: "连接成功" }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<MemoryRouter><SettingsPage /></MemoryRouter>);

    expect(await screen.findByDisplayValue("private-model")).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toHaveValue("");
    expect(screen.getByText("已保存密钥")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));

    expect(await screen.findByText("连接成功 · 支持结构化 JSON")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith("/api/settings/model/test", { method: "POST" });
  });
});

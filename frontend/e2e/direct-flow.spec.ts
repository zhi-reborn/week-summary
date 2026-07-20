import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { uploadAndConfirmInputs } from "./helpers";

test("直接模式分析完成后自动下载有效 Word", async ({ page }, testInfo) => {
  await uploadAndConfirmInputs(page, "direct");

  const downloadLink = page.getByRole("link", { name: "下载汇总 Word" });
  await expect(downloadLink).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "质量提示" })).toBeVisible();
  await expect(page.getByText(/95%/)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await downloadLink.click();
  const download = await downloadPromise;
  const saved = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(saved);
  expect(download.suggestedFilename()).toMatch(/^周报汇总_\d{4}-\d{2}-\d{2}\.docx$/);
  expect(execFileSync(
    path.resolve("../.venv/bin/python"),
    [path.resolve("../scripts/verify_export.py"), saved, "--expect", "统一认证联调"],
    { encoding: "utf8" },
  )).toContain("DOCX_OK");
});

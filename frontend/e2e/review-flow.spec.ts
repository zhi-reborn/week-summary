import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { uploadAndConfirmInputs } from "./helpers";

test("校审模式从上传到下载有效 Word", async ({ page }, testInfo) => {
  await uploadAndConfirmInputs(page, "review");
  await page.getByRole("link", { name: "进入内容校审" }).click();

  await expect(page.getByRole("heading", { name: "周报校审台" })).toBeVisible();
  await page.getByRole("button", { name: "查看来源" }).click();
  await expect(page.getByText(/张三 · 原文第/)).toBeVisible();
  await page.getByRole("button", { name: "关闭来源" }).click();

  const editor = page.getByRole("textbox", { name: "板块内容" });
  await editor.fill("人工校审：本周完成统一认证与模板解析验证。");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByText(/已保存为版本/)).toBeVisible();
  await page.getByRole("button", { name: "确认本板块" }).click();
  await expect(page.getByText(/1 \/ 1 个板块已确认/)).toBeVisible();
  await page.getByRole("button", { name: "生成并下载 Word" }).click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /下载周报汇总_.*\.docx/ }).click();
  const download = await downloadPromise;
  const saved = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(saved);
  expect(download.suggestedFilename()).toMatch(/^周报汇总_\d{4}-\d{2}-\d{2}\.docx$/);
  expect(execFileSync(
    path.resolve("../.venv/bin/python"),
    [path.resolve("../scripts/verify_export.py"), saved, "--expect", "人工校审"],
    { encoding: "utf8" },
  )).toContain("DOCX_OK");
});

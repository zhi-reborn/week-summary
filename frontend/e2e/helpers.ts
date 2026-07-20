import { expect, type Page } from "@playwright/test";
import path from "node:path";

export const reportsPath = path.resolve("e2e/fixtures/team-weekly-report.txt");
export const templatePath = path.resolve("../tests/fixtures/docx/plain_placeholder.docx");

export async function uploadAndConfirmInputs(page: Page, mode: "review" | "direct") {
  await page.goto("/tasks/new/upload");
  await page.getByLabel("汇总名称").fill(`第29周-${mode}`);
  await page.getByRole("radio", { name: mode === "review" ? /校审后生成/ : /直接生成/ }).check();
  await page.getByLabel("合并周报 TXT").setInputFiles(reportsPath);
  await page.getByLabel("Word 模板 DOCX").setInputFiles(templatePath);
  await page.getByRole("button", { name: "上传并识别人员" }).click();

  await expect(page).toHaveURL(/\/tasks\/[^/]+\/people$/);
  await expect(page.getByText("已识别 2 人")).toBeVisible();
  await page.getByRole("button", { name: "确认人员拆分" }).click();
  await expect(page).toHaveURL(/\/tasks\/[^/]+\/template$/);
  await expect(page.getByRole("heading", { name: "本周重点" })).toBeVisible();
  await page.getByRole("button", { name: "确认模板板块" }).click();
  await expect(page).toHaveURL(/\/tasks\/[^/]+\/analysis$/);
}

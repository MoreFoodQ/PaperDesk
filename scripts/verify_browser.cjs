// Run with: node scripts/verify_browser.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PAPERDESK_PLAYWRIGHT || "playwright");

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.PAPERDESK_CHROME ? { executablePath: process.env.PAPERDESK_CHROME } : {}) });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const base = "http://127.0.0.1:8876";
  const token = require('node:child_process').execFileSync(path.join(__dirname, '../.venv/Scripts/python.exe'), ['-c', 'from easyread import config; print(config.server_token())'], {cwd: path.join(__dirname, '..'), encoding: 'utf8'}).trim();
  const pid = fs.readFileSync(path.join(__dirname, "../verification/paper-id.txt"), "utf8").trim();
  await page.goto(base + '/auth?session=' + encodeURIComponent(token));
  await page.locator(".row[data-id='" + pid + "']").waitFor();
  assert.equal(await page.locator("html").getAttribute("lang"), "zh-TW");
  await page.locator("#q").fill("no-such-paper-workbench-test");
  await page.getByText("沒有符合條件的論文", { exact: true }).waitFor();
  await page.locator("#q").fill("");
  await page.locator(".row[data-id='" + pid + "']").click();
  await page.locator("#detail .title-main").waitFor();
  await page.screenshot({ path: path.join(__dirname, "../workbench-library.png") });
  await page.locator(".row[data-id='" + pid + "']").dblclick();
  await page.waitForURL("**/read/" + pid + "**");
  await page.locator("#paper .blk").first().waitFor();
  await page.locator("#chatInput").waitFor();
  await page.locator("#chatInput").fill("請用繁體中文一句話說明這份測試文件的目的。");
  await page.locator("#chatInput").press("Enter");
  await page.waitForFunction(() => {
    const node = document.querySelector("#chatList .cm.ai:last-child .body");
    return node && node.textContent.trim().length > 10 && !document.querySelector("#chatList .thinking");
  }, { timeout: 120000 });
  const answer = await page.locator("#chatList .cm.ai:last-child .body").innerText();
  assert.match(answer, /[\u4e00-\u9fff]/);
  assert.doesNotMatch(answer, /Codex.*出錯|error|failed/i);
  console.log("Live GPT answer:", answer);
  await page.locator('[data-view="both"]').first().click();
  assert(await page.locator("body").evaluate(node => node.classList.contains("mode-bi")));
  await page.screenshot({ path: path.join(__dirname, "../workbench-reader.png") });
  await page.locator('[data-pd-act="notes"]').click();
  assert(await page.locator("body").evaluate(node => node.classList.contains("np-open")));
  await page.locator('[data-pd-act="pages"]').click();
  assert(await page.locator("body").evaluate(node => node.classList.contains("pv-open")));
  await page.locator("#pageview img").waitFor();
  await page.goto(base);
  await page.locator("#langBtn").click();
  await page.waitForFunction(() => document.documentElement.lang === "en");
  assert.equal(await page.locator("#workspaceOverview h1").innerText(), "Research workbench");
  await page.locator("#langBtn").click();
  await page.waitForFunction(() => document.documentElement.lang === "zh-TW");
  for (const width of [980, 390]) {
    await page.setViewportSize({ width, height: 850 });
    await page.goto(base);
    await page.locator(".row").first().waitFor();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    assert.equal(overflow, false, "Library horizontal overflow at " + width);
    await page.screenshot({ path: path.join(__dirname, "../workbench-" + width + ".png") });
  }
  assert.deepEqual(errors, []);
  console.log("Browser checks passed: import view, search, detail, reader, live GPT, bilingual mode, notes, PDF, languages and responsive layouts.");
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

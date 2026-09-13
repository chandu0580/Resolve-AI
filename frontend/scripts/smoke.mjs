/**
 * Phase 8 browser smoke test against the REAL running stack (FastAPI on :8000, Next on :3000).
 *
 *   node scripts/smoke.mjs                 # full run: live scenarios, every route, interactions, screenshots, axe
 *   SMOKE_MODE=api-down node scripts/smoke.mjs   # run with the FastAPI service stopped: error states only
 *
 * Uses the locally installed Microsoft Edge through playwright-core (no browser download) and axe-core.
 * Writes artifacts/phase8/smoke_results.json (or smoke_api_down.json) and artifacts/phase8/screenshots/*.png.
 */
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.CONSOLE_URL ?? "http://127.0.0.1:3000";
const MODE = process.env.SMOKE_MODE ?? "full";
const OUT = path.resolve(here, process.env.SMOKE_OUT ?? "../../artifacts/phase8");   // Phase 9 runs pass SMOKE_OUT so earlier results are not overwritten
const SHOTS = path.join(OUT, "screenshots");
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const RUN_TIMEOUT = 240_000;
fs.mkdirSync(SHOTS, { recursive: true });

const report = { mode: MODE, base: BASE, started: new Date().toISOString(), browser: null, scenarios: [], routes: [], interactions: [], axe: [], overflow: [], consoleErrors: [], failures: [] };
const fail = (msg) => {
  report.failures.push(msg);
  console.error("FAIL", msg);
};

const browser = await chromium.launch({ channel: "msedge", headless: true });
report.browser = `msedge ${browser.version()}`;

async function context(viewport, storageState) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, storageState, permissions: ["clipboard-read", "clipboard-write"] });
  const page = await ctx.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") report.consoleErrors.push({ url: page.url(), text: m.text().slice(0, 300) });
  });
  page.on("pageerror", (e) => report.consoleErrors.push({ url: page.url(), text: String(e).slice(0, 300) }));
  return { ctx, page };
}

async function audit(page, name) {
  await page.addScriptTag({ content: AXE });
  const res = await page.evaluate(() => window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } }));
  const violations = res.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, targets: v.nodes.slice(0, 4).map((n) => n.target.join(" ")) }));
  report.axe.push({ name, url: page.url(), violations });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 1) report.overflow.push({ name, url: page.url(), px: overflow });
}

async function shot(page, name, fullPage = true) {
  // Full-page capture stitches the page while scrolled, which paints sticky bars mid-page; flatten them for the capture only.
  if (fullPage) await page.addStyleTag({ content: '[class*="sticky"]{position:relative!important}' }).catch(() => {});
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage });
}

/**
 * `expectHealthy` (default in the full run) fails the smoke when a page renders one of the console's own error alerts.
 * A Next.js page that shows "the API rejected this request" still answers HTTP 200, so status alone hid a real defect:
 * Analytics asked for 200 more traces than the API allows and the smoke passed anyway.
 */
async function visit(page, route, name, { expectStatus = 200, screenshot = true, axe = true, expectHealthy = MODE === "full" } = {}) {
  const res = await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 60_000 });
  await page.waitForTimeout(400);
  const status = res?.status() ?? 0;
  const h1 = (await page.locator("h1").first().textContent({ timeout: 5_000 }).catch(() => null)) ?? null;
  const alerts = (await appAlerts(page).allTextContents()).filter((a) => a.trim());
  // Navigation timing of the document request (server render included) and the DOM size, for the performance section of the report.
  const timing = await page
    .evaluate(() => {
      const n = performance.getEntriesByType("navigation")[0];
      return n ? { ttfbMs: Math.round(n.responseStart - n.startTime), domContentLoadedMs: Math.round(n.domContentLoadedEventEnd - n.startTime), loadMs: Math.round(n.loadEventEnd - n.startTime), htmlKB: Math.round((n.encodedBodySize || 0) / 1024), domNodes: document.getElementsByTagName("*").length } : null;
    })
    .catch(() => null);
  report.routes.push({ name, route, status, h1, alerts: alerts.map((a) => a.slice(0, 160)), timing });
  if (status !== expectStatus) fail(`${route} answered ${status}, expected ${expectStatus}`);
  if (expectHealthy && alerts.length) fail(`${route} rendered an error state: ${alerts[0].slice(0, 120)}`);
  if (screenshot) await shot(page, name);
  if (axe) await audit(page, name);
  return { status, h1, alerts };
}

// The console's own alerts. Next.js also renders an always-present, empty route announcer with role="alert"; it is excluded.
const appAlerts = (page) => page.locator("main [role=alert]").filter({ hasText: /\S/ });

async function runScenario(page, id) {
  const button = page.getByRole("button", { name: new RegExp(`^Run scenario ${id}:`) });
  const t0 = Date.now();
  await button.click();
  await page.getByRole("status").filter({ hasText: "Running ResolveAI" }).waitFor({ timeout: 10_000 });
  await Promise.race([
    page.getByRole("heading", { name: "Result", exact: true }).waitFor({ timeout: RUN_TIMEOUT }),
    appAlerts(page).first().waitFor({ timeout: RUN_TIMEOUT }),
  ]);
  const ms = Date.now() - t0;
  const alert = await appAlerts(page).first().textContent({ timeout: 1_000 }).catch(() => null);
  if (alert && !(await page.getByRole("heading", { name: "Result", exact: true }).count())) {
    report.scenarios.push({ id, ok: false, ms, error: alert.slice(0, 300) });
    fail(`scenario ${id}: ${alert.slice(0, 200)}`);
    return null;
  }
  const decision = await page.locator("section[aria-label^='Decision:']").first().getAttribute("aria-label");
  const checks = await page.getByRole("list", { name: "Expected versus actual" }).locator("li").allTextContents();
  const traceHref = await page.getByRole("link", { name: "Open trace" }).getAttribute("href");
  const traceId = traceHref?.split("/").pop() ?? null;
  report.scenarios.push({ id, ok: true, ms, decision, expectation: checks.slice(1), traceId });
  return traceId;
}

if (MODE === "unauthorized") {
  // The API requires authentication and this console server has no token: every data page must explain it, never crash or leak detail.
  const { ctx, page } = await context({ width: 1440, height: 900 });
  for (const [route, name] of [
    ["/overview", "unauthorized-overview"],
    ["/traces", "unauthorized-traces"],
    ["/simulate", "unauthorized-simulate"],
    ["/agents", "unauthorized-agents"],
    ["/knowledge", "unauthorized-knowledge"],
  ]) {
    const r = await visit(page, route, name, { axe: route === "/" });
    if (!r.alerts.some((a) => a.includes("Not authorized"))) fail(`${route}: no 'Not authorized' error state`);
  }
  await ctx.close();
} else if (MODE === "api-down") {
  const { ctx, page } = await context({ width: 1440, height: 900 });
  for (const [route, name] of [
    ["/overview", "api-down-overview"],
    ["/traces", "api-down-traces"],
    ["/evaluation", "api-down-evaluation"],
    ["/analytics", "api-down-analytics"],
    ["/simulate", "api-down-simulate"],
    ["/agents", "api-down-agents"],
    ["/settings", "api-down-settings"],
    ["/trust", "api-down-trust"],
  ]) {
    const r = await visit(page, route, name, { axe: route === "/" });
    if (!r.alerts.some((a) => a.includes("ResolveAI API unavailable"))) fail(`${route}: no 'API unavailable' error state`);
  }
  const status = await page.locator("aside").getByText("API unavailable").count();
  report.interactions.push({ name: "sidebar agent status shows API unavailable", ok: status > 0 });
  await ctx.close();
} else {
  // 1. Live simulation on desktop: run every scenario the live API can reproduce, and one custom message.
  const desktop = await context({ width: 1440, height: 900 });
  const page = desktop.page;
  // Before anything has run: the console must show truthful empty states, not invented activity.
  const before = await (await fetch(`${BASE}/api/v1/traces?limit=1`)).json().catch(() => null);
  report.traceStoreEmptyAtStart = Array.isArray(before?.items) && before.items.length === 0;
  if (report.traceStoreEmptyAtStart) {
    await visit(page, "/", "empty-overview");
    await visit(page, "/conversations", "empty-conversations", { axe: false });
    await visit(page, "/knowledge", "empty-knowledge", { axe: false });
  }
  await visit(page, "/simulate", "simulate-empty");
  const traces = {};
  for (const id of ["A", "B", "C", "D", "E", "G"]) {
    traces[id] = await runScenario(page, id);
    if (id === "A") await shot(page, "simulate-result-A-auto-handle");
    if (id === "C") await shot(page, "simulate-result-C-security-handoff");
    if (id === "D") await shot(page, "simulate-result-D-clarification");
  }
  await page.getByLabel("Customer message").fill("I was charged twice for my Apple Music subscription this month and want the extra charge refunded");
  const t0 = Date.now();
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "Running ResolveAI" }).waitFor({ timeout: 10_000 });
  await shot(page, "simulate-running", false);
  await page.getByRole("heading", { name: "Result", exact: true }).waitFor({ timeout: RUN_TIMEOUT });
  const customDecision = await page.locator("section[aria-label^='Decision:']").first().getAttribute("aria-label");
  const customHref = await page.getByRole("link", { name: "Open trace" }).getAttribute("href");
  report.scenarios.push({ id: "custom-billing", ok: true, ms: Date.now() - t0, decision: customDecision, traceId: customHref?.split("/").pop() });
  await shot(page, "simulate-result-custom-billing");

  // 2. Every route, with the results of this browser session available.
  await visit(page, "/", "landing");
  await visit(page, "/overview", "overview");
  await visit(page, "/conversations", "conversations");
  await page.getByRole("button", { name: /^Human handoff/ }).click();
  report.interactions.push({ name: "conversation filter updates URL", ok: page.url().includes("filter=handoff"), url: page.url() });
  await shot(page, "conversations-filter-handoff");

  if (traces.A) {
    await visit(page, `/conversations/${traces.A}`, "conversation-A-workspace");
    const evidenceToggle = page.locator("article[id^='evidence-']").first().getByRole("button", { name: "Why selected" });
    await evidenceToggle.click();
    report.interactions.push({ name: "evidence card expands", ok: (await evidenceToggle.getAttribute("aria-expanded")) === "true" });
    const policyStage = page.getByRole("button", { name: /^Policy/ }).first();
    await policyStage.click();
    report.interactions.push({ name: "trace stage expands", ok: (await policyStage.getAttribute("aria-expanded")) === "true" });
    report.interactions.push({ name: "workspace explains why the response was allowed", ok: (await page.getByText("Why this response was allowed").count()) > 0 });
    report.interactions.push({ name: "workspace separates evidence used from retrieved", ok: (await page.getByRole("region", { name: "Evidence used in response" }).count()) > 0 });
    report.interactions.push({ name: "workspace has a conversation list", ok: (await page.getByRole("navigation", { name: "Conversations" }).count()) > 0 });
    await shot(page, "conversation-A-workspace-expanded");
  }
  if (traces.D) await visit(page, `/conversations/${traces.D}`, "conversation-D-clarification");
  await visit(page, "/handoffs", "handoffs");
  await page.getByRole("group", { name: "Filter handoffs by queue" }).getByRole("button", { name: /^Security/ }).click();
  report.interactions.push({ name: "handoff queue filter selects Security", ok: (await page.getByRole("button", { name: /^Security/, pressed: true }).count()) > 0 });
  await shot(page, "handoffs-filter-security", false);
  if (traces.C) {
    await visit(page, `/handoffs/${traces.C}`, "handoff-C-detail");
    await page.getByRole("button", { name: "Copy handoff summary" }).click();
    const copied = await page.getByRole("button", { name: "Copied" }).waitFor({ timeout: 3_000 }).then(() => true, () => false);
    const clip = copied ? await page.evaluate(() => navigator.clipboard.readText()).catch(() => "") : "";
    report.interactions.push({ name: "copy handoff summary", ok: copied && clip.includes(traces.C), chars: clip.length });
  }
  await visit(page, "/knowledge", "knowledge");
  await visit(page, "/traces", "traces");
  if (traces.A) await visit(page, `/traces/${traces.A}`, "trace-A-timeline");
  if (traces.E) await visit(page, `/traces/${traces.E}`, "trace-E-injection");
  await visit(page, "/evaluation", "evaluation");
  await visit(page, "/analytics", "analytics");
  await page.goto(`${BASE}/evaluation#misleading-headline`, { waitUntil: "networkidle" });
  await shot(page, "evaluation-misleading-headline", false);
  await visit(page, "/trust", "trust");
  await visit(page, "/agents", "agents");
  await visit(page, "/settings", "settings");
  const settingsText = (await page.locator("main").textContent()) ?? "";
  report.interactions.push({ name: "settings never renders a token value", ok: !/Bearer\s+\S{16,}/.test(settingsText) && !(process.env.RESOLVEAI_API_TOKEN && settingsText.includes(process.env.RESOLVEAI_API_TOKEN)) });
  await visit(page, "/traces/00000000000000000000000000000000", "error-unknown-trace", { expectHealthy: false });
  await visit(page, "/traces/not-a-trace-id", "error-invalid-trace-id", { axe: false, expectHealthy: false });
  await visit(page, "/this-page-does-not-exist", "error-404", { expectStatus: 404, axe: false });

  // Global search: a trace id jumps to its trace.
  if (traces.B) {
    await page.goto(`${BASE}/overview`, { waitUntil: "networkidle" });
    await page.getByLabel("Search conversations and intents, or paste a trace id").fill(traces.B);
    await page.keyboard.press("Enter");
    await page.waitForURL(`**/traces/${traces.B}`, { timeout: 15_000 }).catch(() => null);
    report.interactions.push({ name: "search by trace id opens the trace", ok: page.url().endsWith(`/traces/${traces.B}`) });
  }

  // Trace-only view: a trace whose full result is not in this browser.
  const fresh = await context({ width: 1440, height: 900 });
  if (traces.C) await visit(fresh.page, `/conversations/${traces.C}`, "conversation-C-trace-only");
  await fresh.ctx.close();

  // Keyboard: the skip link is the first tab stop.
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => document.activeElement?.textContent?.trim());
  report.interactions.push({ name: "skip link is first tab stop", ok: focused === "Skip to content", focused });

  const state = await desktop.ctx.storageState();
  await desktop.ctx.close();

  // 3. Tablet, narrow desktop and mobile.
  for (const [label, viewport] of [
    ["tablet", { width: 834, height: 1112 }],
    ["narrow", { width: 1180, height: 820 }],
    ["mobile", { width: 390, height: 844 }],
  ]) {
    const { ctx, page: p } = await context(viewport, state);
    await visit(p, "/", `${label}-overview`);
    if (traces.A) await visit(p, `/conversations/${traces.A}`, `${label}-conversation-A`);
    await visit(p, "/conversations", `${label}-conversations`, { axe: false });
    await visit(p, "/evaluation", `${label}-evaluation`, { axe: false });
    await visit(p, "/handoffs", `${label}-handoffs`, { axe: false });
    await visit(p, "/agents", `${label}-agents`, { axe: false });
    await visit(p, "/knowledge", `${label}-knowledge`, { axe: false });
    if (label === "mobile") {
      await p.goto(`${BASE}/overview`, { waitUntil: "networkidle" });
      await p.getByRole("button", { name: "Open navigation" }).click();
      const open = await p.getByRole("dialog", { name: "Navigation" }).isVisible();
      await shot(p, "mobile-navigation-open", false);
      await p.keyboard.press("Escape");
      const closed = !(await p.getByRole("dialog", { name: "Navigation" }).count());
      report.interactions.push({ name: "mobile navigation opens and closes with Escape", ok: open && closed });
    }
    await ctx.close();
  }
}

await browser.close();
report.finished = new Date().toISOString();
report.summary = {
  routes: report.routes.length,
  scenarios: report.scenarios.length,
  scenarioFailures: report.scenarios.filter((s) => !s.ok).length,
  interactionsFailed: report.interactions.filter((i) => !i.ok).map((i) => i.name),
  axeViolations: report.axe.reduce((n, a) => n + a.violations.length, 0),
  pagesWithOverflow: report.overflow.length,
  consoleErrors: report.consoleErrors.length,
  failures: report.failures.length,
};
const file = path.join(OUT, MODE === "api-down" ? "smoke_api_down.json" : MODE === "unauthorized" ? "smoke_unauthorized.json" : "smoke_results.json");
fs.writeFileSync(file, JSON.stringify(report, null, 1) + "\n");
console.log(JSON.stringify(report.summary, null, 1));
console.log("wrote", file);
process.exit(report.failures.length || report.summary.interactionsFailed.length ? 1 : 0);

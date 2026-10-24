// Render the Instagram flyers to 1080 x 1440 PNGs (3:4 portrait feed posts).
// Usage: node render-instagram.js [01 02 03 04]   (needs playwright-core and Chrome)
const path = require("path");
const { chromium } = require(process.env.PW_CORE || "playwright-core");

const ids = process.argv.slice(2).length ? process.argv.slice(2) : ["01", "02", "03", "04"];
const DIR = __dirname;
const W = 1080, H = 1440;

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe",
    headless: true,
  });
  for (const id of ids) {
    const name = `Ribdigi_ERP_Instagram_Flyer_${id}`;
    const url = "file:///" + path.join(DIR, `${name}.html`).replace(/\\/g, "/");
    const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);
    // Report anything that spills outside the post or its safe margin.
    const issues = await page.evaluate(() => {
      const out = [];
      const safe = 60;
      for (const el of document.querySelectorAll(".post *")) {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height || el.closest("[data-bleed]")) continue;
        const text = (el.childElementCount === 0 && el.textContent.trim()) || "";
        if (text && (r.left < safe || r.right > 1080 - safe || r.top < safe || r.bottom > 1440 - safe)) {
          out.push(`${text.slice(0, 30)} @ ${Math.round(r.left)},${Math.round(r.top)}-${Math.round(r.right)},${Math.round(r.bottom)}`);
        }
        if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow === "visible" && text) {
          out.push(`overflow: ${text.slice(0, 30)}`);
        }
      }
      return out;
    });
    await page.screenshot({ path: path.join(DIR, `${name}.png`), clip: { x: 0, y: 0, width: W, height: H } });
    await ctx.close();
    console.log("rendered", name, issues.length ? "\n  " + issues.join("\n  ") : "(text inside safe margin)");
  }
  await browser.close();
})();

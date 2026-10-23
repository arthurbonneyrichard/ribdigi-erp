// Render each flyer HTML to a 300 dpi PNG and a print-ready A4 PDF.
// Usage: node render.js [01 02 03 04]   (needs playwright-core and Chrome)
const path = require("path");
const { chromium } = require(process.env.PW_CORE || "playwright-core");

const ids = process.argv.slice(2).length ? process.argv.slice(2) : ["01", "02", "03", "04"];
const DIR = __dirname;
// A4 at 96 css px per inch is 793.7 x 1122.5 px; scale 3.125 gives 300 dpi (2480 x 3508).
const W = 794, H = 1123, SCALE = 300 / 96;

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe",
    headless: true,
  });
  for (const id of ids) {
    const name = `Ribdigi_ERP_Launch_Flyer_${id}`;
    const url = "file:///" + path.join(DIR, `${name}.html`).replace(/\\/g, "/");
    const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: SCALE });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(DIR, `${name}.png`), clip: { x: 0, y: 0, width: W, height: H } });
    await page.pdf({ path: path.join(DIR, `${name}.pdf`), format: "A4", printBackground: true, preferCSSPageSize: true });
    await ctx.close();
    console.log("rendered", name);
  }
  await browser.close();
})();

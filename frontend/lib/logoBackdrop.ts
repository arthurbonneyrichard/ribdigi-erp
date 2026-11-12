/**
 * Pick the sidebar backdrop that makes a logo stand out.
 *
 * A logo with its own solid background (the default RIBDIGI mark on black) gets that same
 * colour, so the box and the image read as one. A logo on a transparent background gets the
 * candidate colour that gives most of its visible pixels the strongest contrast: white, near
 * black, the brand forest, or light and deep shades of the logo's own hue and its opposite.
 */

export type Rgb = [number, number, number];
export type Pixel = { rgb: Rgb; alpha: number };
export type Backdrop = { background: string; border: string; text: string; subtext: string };

const FOREST: Rgb = [0, 61, 31];

function channel(v: number): number {
  const c = v / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export function hex([r, g, b]: Rgb): string {
  return `#${[r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('')}`;
}

function hslToRgb(h: number, s: number, l: number): Rgb {
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0) * 255, f(8) * 255, f(4) * 255];
}

function rgbToHue([r, g, b]: Rgb): { h: number; s: number } {
  const rr = r / 255;
  const gg = g / 255;
  const bb = b / 255;
  const max = Math.max(rr, gg, bb);
  const min = Math.min(rr, gg, bb);
  const d = max - min;
  if (d === 0) return { h: 0, s: 0 };
  let h = 0;
  if (max === rr) h = ((gg - bb) / d) % 6;
  else if (max === gg) h = (bb - rr) / d + 2;
  else h = (rr - gg) / d + 4;
  const l = (max + min) / 2;
  return { h: (h * 60 + 360) % 360, s: d / (1 - Math.abs(2 * l - 1)) };
}

/** Text that reads on the chosen background. */
function finish(bg: Rgb): Backdrop {
  const dark = luminance(bg) < 0.35;
  const edge: Rgb = dark ? [bg[0] + 28, bg[1] + 28, bg[2] + 28] : [bg[0] - 30, bg[1] - 30, bg[2] - 30];
  return {
    background: hex(bg),
    border: hex(edge),
    text: dark ? '#E8F5D0' : '#10211B',
    subtext: dark ? '#B7C9BE' : '#4D5D56',
  };
}

/** The logo's own background: the frame of pixels round the edge, when it is solid and even. */
export function solidFrame(edge: Pixel[]): Rgb | null {
  if (edge.length === 0) return null;
  const solid = edge.filter((p) => p.alpha > 230);
  if (solid.length < edge.length * 0.9) return null;
  const mean: Rgb = [0, 1, 2].map((i) => solid.reduce((sum, p) => sum + p.rgb[i], 0) / solid.length) as Rgb;
  const even = solid.filter((p) => Math.max(...p.rgb.map((v, i) => Math.abs(v - mean[i]))) < 24);
  return even.length >= solid.length * 0.85 ? mean : null;
}

export function chooseBackdrop(pixels: Pixel[], edge: Pixel[] = []): Backdrop {
  const frame = solidFrame(edge);
  if (frame) return finish(frame);

  const ink = pixels.filter((p) => p.alpha > 128).map((p) => p.rgb);
  if (ink.length === 0) return finish([0, 0, 0]);

  // The logo's main hue, from its colourful pixels.
  const colourful = ink.map((rgb) => ({ rgb, ...rgbToHue(rgb) })).filter((p) => p.s > 0.25);
  const candidates: Rgb[] = [[255, 255, 255], [245, 247, 236], [11, 15, 13], FOREST];
  if (colourful.length >= ink.length * 0.1) {
    const x = colourful.reduce((sum, p) => sum + Math.cos((p.h * Math.PI) / 180), 0);
    const y = colourful.reduce((sum, p) => sum + Math.sin((p.h * Math.PI) / 180), 0);
    const hue = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
    const opposite = (hue + 180) % 360;
    candidates.push(hslToRgb(hue, 0.45, 0.95), hslToRgb(hue, 0.5, 0.12), hslToRgb(opposite, 0.45, 0.94), hslToRgb(opposite, 0.5, 0.14));
  }

  // Group the colours; every colour that makes up a fair share of the logo must stand out,
  // so a thin dark word is not lost next to a big bright shape. The weakest group decides;
  // the average breaks ties.
  const buckets = new Map<string, { sum: Rgb; n: number }>();
  for (const rgb of ink) {
    const key = rgb.map((v) => v >> 5).join(',');
    const row = buckets.get(key) || { sum: [0, 0, 0] as Rgb, n: 0 };
    row.sum = [row.sum[0] + rgb[0], row.sum[1] + rgb[1], row.sum[2] + rgb[2]];
    row.n += 1;
    buckets.set(key, row);
  }
  const groups = Array.from(buckets.values())
    .filter((g) => g.n >= ink.length * 0.04)
    .map((g) => ({ rgb: g.sum.map((v) => v / g.n) as Rgb, share: g.n / ink.length }));
  let best = candidates[0];
  let bestScore = -1;
  let bestMean = -1;
  for (const bg of candidates) {
    const ratios = groups.map((g) => contrast(g.rgb, bg));
    const worst = Math.min(...ratios);
    const mean = groups.reduce((sum, g, i) => sum + g.share * ratios[i], 0);
    if (worst > bestScore + 0.05 || (Math.abs(worst - bestScore) <= 0.05 && mean > bestMean)) {
      best = bg;
      bestScore = worst;
      bestMean = mean;
    }
  }
  return finish(best);
}

/** Read the loaded logo through a small canvas. Null when the browser will not allow it. */
export function backdropForImage(img: HTMLImageElement): Backdrop | null {
  try {
    const w = Math.max(1, Math.min(96, img.naturalWidth));
    const h = Math.max(1, Math.round((img.naturalHeight / Math.max(1, img.naturalWidth)) * w));
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, w, h);
    const data = ctx.getImageData(0, 0, w, h).data;
    const alphaAt = (x: number, y: number) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : data[(y * w + x) * 4 + 3]);
    const pixels: Pixel[] = [];
    const outline: Pixel[] = [];
    const edge: Pixel[] = [];
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const i = (y * w + x) * 4;
        const px: Pixel = { rgb: [data[i], data[i + 1], data[i + 2]], alpha: data[i + 3] };
        pixels.push(px);
        if (x === 0 || y === 0 || x === w - 1 || y === h - 1) edge.push(px);
        // Only the logo's outline meets the box: colours inside a shape do not need to stand out from it.
        const near = [alphaAt(x - 1, y), alphaAt(x + 1, y), alphaAt(x, y - 1), alphaAt(x, y + 1), alphaAt(x - 2, y), alphaAt(x + 2, y)];
        if (px.alpha > 128 && near.some((a) => a < 64)) outline.push(px);
      }
    }
    return chooseBackdrop(outline.length >= 12 ? outline : pixels, edge);
  } catch {
    return null;
  }
}

const CACHE_PREFIX = 'ribdigi:logo-backdrop:';

export function cachedBackdrop(key: string): Backdrop | null {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + key);
    return raw ? (JSON.parse(raw) as Backdrop) : null;
  } catch {
    return null;
  }
}

export function rememberBackdrop(key: string, value: Backdrop): void {
  try {
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(value));
  } catch {
    /* only saves a flash on the next visit */
  }
}

/**
 * Banner generator — creates a 1200×600 social/README banner using node-canvas.
 *
 * Usage:
 *   cd web && npx ts-node ../scripts/banner.ts
 *
 * Requires:
 *   npm install canvas
 *   (canvas has native bindings — see https://www.npmjs.com/package/canvas)
 *
 * Output: docs/screenshots/banner.png
 */

import { createCanvas, loadImage } from "canvas";
import * as fs from "fs";
import * as path from "path";

const W = 1200;
const H = 600;
const OUT = path.resolve(__dirname, "../docs/screenshots/banner.png");

// Color palette (matches globals.css dark theme)
const BG           = "#0f172a"; // slate-950
const ACCENT       = "#22d3ee"; // cyan-400
const TEXT_PRIMARY = "#f1f5f9"; // slate-100
const TEXT_MUTED   = "#94a3b8"; // slate-400
const GRID_LINE    = "#1e293b"; // slate-800

async function run() {
  const canvas = createCanvas(W, H);
  const ctx    = canvas.getContext("2d");

  // ── Background ──────────────────────────────────────────────────────────
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, W, H);

  // Subtle grid overlay
  ctx.strokeStyle = GRID_LINE;
  ctx.lineWidth   = 1;
  for (let x = 0; x < W; x += 80) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = 0; y < H; y += 80) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }

  // ── Cyan accent bar (left edge) ─────────────────────────────────────────
  ctx.fillStyle = ACCENT;
  ctx.fillRect(0, 0, 6, H);

  // ── Text block (left side) ──────────────────────────────────────────────
  const LEFT = 72;

  // Tag
  ctx.fillStyle = ACCENT;
  ctx.font      = "bold 14px monospace";
  ctx.fillText("OPEN SOURCE · RESEARCH PREVIEW", LEFT, 120);

  // Title
  ctx.fillStyle = TEXT_PRIMARY;
  ctx.font      = "bold 72px sans-serif";
  ctx.fillText("OpenOncology", LEFT, 210);

  // Tagline
  ctx.fillStyle = TEXT_MUTED;
  ctx.font      = "24px sans-serif";
  ctx.fillText("AI-powered mutation analysis &", LEFT, 265);
  ctx.fillText("personalised drug discovery", LEFT, 300);

  // Key stats row
  const stats = [
    { label: "OncoKB Level 1", value: "Actionable" },
    { label: "TCGA Validated", value: "200 cases" },
    { label: "Top-1 Concordance", value: "82 %" },
  ];
  let sx = LEFT;
  for (const s of stats) {
    ctx.fillStyle = ACCENT;
    ctx.font      = "bold 22px sans-serif";
    ctx.fillText(s.value, sx, 385);
    ctx.fillStyle = TEXT_MUTED;
    ctx.font      = "13px sans-serif";
    ctx.fillText(s.label, sx, 408);
    sx += 220;
  }

  // URL
  ctx.fillStyle = TEXT_MUTED;
  ctx.font      = "14px monospace";
  ctx.fillText("github.com/immortal71/openoncology", LEFT, 480);

  // ── Right panel: screenshot composites ──────────────────────────────────
  const SCREENSHOTS_DIR = path.resolve(__dirname, "../docs/screenshots");
  const tiles: { file: string; x: number; y: number }[] = [
    { file: "results.png",     x: 680, y:  40 },
    { file: "repurposing.png", x: 940, y:  40 },
    { file: "custom-drug.png", x: 680, y: 310 },
    { file: "marketplace.png", x: 940, y: 310 },
  ];

  for (const t of tiles) {
    const fp = path.join(SCREENSHOTS_DIR, t.file);
    if (!fs.existsSync(fp)) {
      // Draw placeholder
      ctx.fillStyle = GRID_LINE;
      ctx.fillRect(t.x, t.y, 240, 240);
      ctx.fillStyle = TEXT_MUTED;
      ctx.font      = "11px monospace";
      ctx.fillText(t.file, t.x + 8, t.y + 20);
      continue;
    }
    try {
      const img = await loadImage(fp);
      // Clip to rounded rect
      ctx.save();
      ctx.beginPath();
      roundRect(ctx, t.x, t.y, 240, 240, 10);
      ctx.clip();
      ctx.drawImage(img, t.x, t.y, 240, 240);
      ctx.restore();
      // Drop shadow border
      ctx.strokeStyle = GRID_LINE;
      ctx.lineWidth   = 2;
      ctx.beginPath();
      roundRect(ctx, t.x, t.y, 240, 240, 10);
      ctx.stroke();
    } catch {
      // loadImage failed — draw placeholder
      ctx.fillStyle = GRID_LINE;
      ctx.fillRect(t.x, t.y, 240, 240);
    }
  }

  // ── Save ─────────────────────────────────────────────────────────────────
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const buffer = canvas.toBuffer("image/png");
  fs.writeFileSync(OUT, buffer);
  console.log(`Banner saved → ${OUT}`);
}

/** Helper: draws a rounded-rect path without ctx.roundRect (not in node-canvas 2.x) */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number
) {
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y,         x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h,     x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x,     y + h,     x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x,     y,         x + r, y);
  ctx.closePath();
}

run().catch((err) => { console.error(err); process.exit(1); });

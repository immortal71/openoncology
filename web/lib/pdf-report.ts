import { jsPDF } from "jspdf";
import { levelApplies, NEAR_TIE, type WsCandidate, type WsCase } from "@/lib/workspace";

const MARGIN = 48;
const WIDTH = 595.28 - MARGIN * 2; // A4 width in points, minus margins

/** Builds and downloads a PDF from the exact same fields the on-screen detail panel
    shows for this candidate — no content here that isn't already rendered in the UI. */
export function downloadCaseReport(ws: WsCase, c: WsCandidate) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  let y = MARGIN;

  const line = (text: string, size: number, opts: { bold?: boolean; color?: [number, number, number]; gap?: number } = {}) => {
    doc.setFont("helvetica", opts.bold ? "bold" : "normal");
    doc.setFontSize(size);
    doc.setTextColor(...(opts.color ?? [36, 33, 43]));
    const wrapped = doc.splitTextToSize(text, WIDTH);
    for (const row of wrapped) {
      if (y > 780) {
        doc.addPage();
        y = MARGIN;
      }
      doc.text(row, MARGIN, y);
      y += size * 1.35;
    }
    y += opts.gap ?? 6;
  };

  const section = (title: string, body: string) => {
    line(title.toUpperCase(), 10, { bold: true, color: [98, 94, 104], gap: 3 });
    line(body, 11, { gap: 14 });
  };

  line(`${ws.title} · ${ws.tumor}`, 18, { bold: true, gap: 2 });
  line("Evidence review", 11, { color: [98, 94, 104], gap: 14 });

  if (ws.demo) line("Demo case · not a real patient", 10, { color: [158, 74, 58], gap: 2 });
  line("Research prototype, not a medical device. Every result needs oncologist review.", 9.5, { color: [98, 94, 104], gap: 18 });

  const applies = levelApplies(c, ws.lead);
  const evidenceLabel = applies && ws.lead?.level ? ws.lead.level.label : (c.tierInfo.badge ?? "—");

  line(`Selected candidate: ${c.name}`, 15, { bold: true, gap: 2 });
  line(`${ws.title} · ${ws.tumor}`, 10.5, { color: [98, 94, 104], gap: 10 });

  line(`Score ${c.score !== null ? c.score.toFixed(2) : "—"}   ·   Rank ${c.rank} of ${ws.candidates.length}   ·   Evidence ${evidenceLabel}`, 11, { bold: true, gap: 4 });
  const tie = ws.nearTies.find((t) => t.name === c.name || t.above === c.name);
  let rankingNote = "Ranks candidates within this case. It is not a response probability.";
  if (tie) rankingNote += ` ${tie.name} scores within ${NEAR_TIE} of ${tie.above}: treat the pair as a near-tie.`;
  line(rankingNote, 9.5, { color: [98, 94, 104], gap: 16 });

  const whyItAppears =
    applies && ws.lead?.level
      ? `${ws.lead.level.label} · ${ws.lead.name}. ${ws.lead.level.meaning}${c.matched.length ? ` Matched on ${c.matched.join(", ")}.` : ""}`
      : `${c.tierInfo.note ?? c.tierInfo.heading}${c.matched.length ? ` Matched on ${c.matched.join(", ")}.` : ""}`;
  section("Why it appears", whyItAppears);

  const approvalNote = c.approval.qualifier ? `indication: ${c.approval.qualifier}` : "indication not stored in this result";
  section("Approval", `${c.approval.label}, as reported · ${approvalNote}`);

  section("Side effects", "Not supplied in this result — no adverse-event source is wired into the ranking pipeline yet.");

  section("Sources", `${c.sources.length ? c.sources.join(", ") : "No verified source on this row"}. Exact lookup record not stored in this result.`);

  section("Mechanism", c.mechanism ?? "Not reported");

  if (c.chembl) section("Identifiers", c.chembl);

  line("Oncologist sign-off: Pending", 10.5, { bold: true, gap: 2 });
  line(`Generated ${new Date().toLocaleString()} from the on-screen result. Not a stored clinical document.`, 8.5, { color: [143, 137, 153], gap: 0 });

  const safeTitle = ws.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  doc.save(`${safeTitle}-${c.name.toLowerCase()}-evidence-review.pdf`);
}

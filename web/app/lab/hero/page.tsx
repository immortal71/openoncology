import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Info } from "lucide-react";
import { TrackMark, Wordmark } from "@/components/brand/marks";
import { displayFont } from "@/lib/display-font";
import { DEMO_REPURPOSING, DEMO_RESULTS } from "@/lib/demo-data";
import { ScaledStage } from "./ScaledStage";

export const metadata: Metadata = {
  title: "Hero lab | OpenOncology",
  robots: { index: false, follow: false },
};

const HEADLINE_LEAD = "From a tumor VCF to a ";
const HEADLINE_ACCENT = "ranked";
const HEADLINE_TAIL = " drug list, with its evidence sources named.";
const SUBHEAD =
  "OpenOncology ranks approved drugs and repurposing candidates against a tumor's mutation profile, and names the sources behind every ranking.";
const REVIEW_NOTE = "Research prototype. Oncologist review is required before any treatment decision.";
const SEQUENCE = "GTTGGAGCTGGTGGCGTAGGCAAGAGTGCC";
const C34 = 9;
const CHROMOSOMES = [100, 97, 81, 77, 74, 70, 65, 59, 56, 54, 55, 54, 46, 43, 41, 37, 33, 32, 24, 26, 19, 21, 63];
const SOURCES_PENDING_REVIEW = new Set(["DiffDock"]);

const kras = DEMO_RESULTS.mutations[0];
const ranked = [...DEMO_REPURPOSING.candidates].sort((a, b) => (b.rank_score ?? 0) - (a.rank_score ?? 0));
const tierLabel: Record<string, string> = { fda_approved: "FDA approved", repurposed: "Repurposed" };
const levelLabel = (level: string) => `OncoKB Level ${level.replace("LEVEL_", "")}`;

type Candidate = (typeof ranked)[number];

function sourcesOf(c: Candidate) {
  return c.evidence_sources
    .filter((s) => !SOURCES_PENDING_REVIEW.has(s))
    .map((s) => {
      if (s === "OpenTargets" && c.opentargets_score != null) return `OpenTargets ${c.opentargets_score.toFixed(2)}`;
      if (s === "ClinicalPhase") return "Clinical phase";
      return s;
    });
}

type HeroState = "load" | "flat" | "unpacked";

function Nav() {
  return (
    <div className="flex h-[72px] items-center justify-between border-b border-oo-line px-24">
      <span className="flex items-center gap-2.5">
        <TrackMark size={28} />
        <Wordmark size={21} />
      </span>
      <span className="flex items-center gap-9 text-[15px] text-oo-ink-2">
        <span>Product</span>
        <span>Methods</span>
        <span>Community</span>
        <span className="rounded-full bg-oo-hema px-5 py-2.5 text-[15px] font-semibold text-white">Request access</span>
      </span>
    </div>
  );
}

function DemoTag() {
  return (
    <span className="inline-flex rounded-full border border-oo-line bg-oo-surface px-3 py-1 font-mono text-[12px] text-oo-ink-3">
      Demo case · KRAS G12C · {DEMO_RESULTS.cancer_type}
    </span>
  );
}

function HeroCopy({ phone = false }: { phone?: boolean }) {
  return (
    <div className={phone ? "space-y-4" : "space-y-6"}>
      <span className="inline-flex rounded-full border border-oo-line bg-oo-surface px-3 py-1 text-[13px] font-medium text-oo-ink-3">
        Research prototype · Open source
      </span>
      <h1
        className={`font-display font-semibold tracking-[-0.02em] text-oo-ink ${phone ? "text-[34px] leading-[1.08]" : "text-[64px] leading-[1.05]"}`}
      >
        {HEADLINE_LEAD}
        <span className="text-oo-hema">{HEADLINE_ACCENT}</span>
        {HEADLINE_TAIL}
      </h1>
      <p className={`leading-relaxed text-oo-ink-2 ${phone ? "text-[16px]" : "max-w-[500px] text-[18px]"}`}>{SUBHEAD}</p>
      <div className="flex flex-wrap items-center gap-3">
        <span className={`rounded-full bg-oo-hema font-semibold text-white ${phone ? "px-5 py-3 text-[15px]" : "px-6 py-3.5 text-[16px]"}`}>
          View the demo case
        </span>
        {phone ? null : (
          <span className="rounded-full border border-oo-line bg-oo-surface px-6 py-3.5 text-[16px] font-semibold text-oo-ink">Read the methods</span>
        )}
      </div>
      <DemoTag />
    </div>
  );
}

function Track({ annotated }: { annotated: boolean }) {
  const exons = [
    { x: 20, w: 30 },
    { x: 78, w: 46 },
    { x: 150, w: 34 },
    { x: 212, w: 52 },
    { x: 292, w: 40 },
    { x: 356, w: 48 },
  ];
  return (
    <div className="rounded-xl border border-oo-line bg-oo-surface px-4 pb-3 pt-2">
      <div className="flex justify-between text-[11px] text-oo-muted">
        <span>KRAS · schematic, not to scale</span>
        <span className="font-mono">6 exons</span>
      </div>
      <svg viewBox="0 0 420 120" className="mt-1 h-auto w-full" aria-hidden="true">
        <rect x="10" y="84" width="400" height="3" rx="1.5" fill="rgb(var(--oo-line))" />
        {exons.map((e) => (
          <rect key={e.x} x={e.x} y="72" width={e.w} height="28" rx="6" fill="rgb(var(--oo-ink))" opacity="0.85" />
        ))}
        <rect x="98" y="22" width="5" height="62" rx="2.5" fill="rgb(var(--oo-eosin))" />
        <circle cx="100.5" cy="22" r="11" fill="rgb(var(--oo-eosin))" />
        {annotated ? (
          <>
            <text x="122" y="20" fontSize="16" fontWeight="600" fill="rgb(var(--oo-ink))" fontFamily="var(--font-plex)">
              {`KRAS ${kras.hgvs}`}
            </text>
            <text x="122" y="40" fontSize="13" fill="rgb(var(--oo-ink-3))" fontFamily="var(--font-plex)">
              {`${levelLabel(kras.oncokb_level)} · ${kras.classification}`}
            </text>
          </>
        ) : null}
      </svg>
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="h-1.5 w-[110px] rounded-full bg-oo-line-soft">
        <span className="block h-1.5 origin-left rounded-full bg-oo-hema" style={{ transform: `scaleX(${score})` }} />
      </span>
      <span className="w-10 text-right font-mono text-[13px] tabular-nums text-oo-ink-3">{score.toFixed(2)}</span>
    </span>
  );
}

function ResultsCard({ state, phone = false }: { state: HeroState; phone?: boolean }) {
  const expanded = state === "unpacked" && !phone;
  const tilt = state === "load" && !phone ? "perspective(1400px) rotateX(12deg) scale(0.92)" : "none";
  return (
    <div
      className={`rounded-2xl border border-oo-line bg-oo-surface shadow-[0_40px_80px_-40px_rgba(27,22,38,0.28)] ${phone ? "p-4" : "p-6"}`}
      style={{ transform: tilt, transformOrigin: "50% 0%" }}
    >
      <div className="flex items-center justify-between">
        <span className={`font-semibold text-oo-ink ${phone ? "text-[15px]" : "text-[17px]"}`}>Ranked candidates</span>
        <span className="rounded-full bg-oo-status-complete-bg px-2.5 py-1 text-[12px] font-semibold text-oo-status-complete-fg">Complete</span>
      </div>
      <p className={`mt-2 leading-relaxed text-oo-ink-2 ${phone ? "text-[13px]" : "text-[14px]"}`}>{DEMO_RESULTS.patient_summary.explanation}</p>
      <div className={`mt-4 ${expanded ? "space-y-3" : "space-y-2"}`}>
        {ranked.map((c, i) => (
          <div key={c.chembl_id} className="rounded-xl border border-oo-line-soft px-3.5 py-2.5">
            <div className="flex items-center gap-3">
              <span className="w-4 font-mono text-[12px] text-oo-muted">{i + 1}</span>
              <span className={`min-w-[11ch] font-semibold text-oo-ink ${phone ? "text-[14px]" : "text-[15px]"}`}>{c.drug_name}</span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${
                  c.drug_tier === "fda_approved" ? "bg-oo-hema-tint text-oo-hema" : "bg-oo-line-soft text-oo-ink-2"
                }`}
              >
                {tierLabel[c.drug_tier] ?? c.drug_tier}
              </span>
              <span className="ml-auto">
                <ScoreBar score={c.rank_score ?? 0} />
              </span>
            </div>
            {expanded ? (
              <div className="mt-2.5 space-y-2 pl-7">
                <div className="text-[13px] text-oo-ink-3">
                  {c.approval_status} · {c.mechanism}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {sourcesOf(c).map((s) => (
                    <span key={s} className="rounded-md border border-oo-line px-2 py-0.5 font-mono text-[12px] text-oo-ink-2">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function ReviewNote({ phone = false }: { phone?: boolean }) {
  return (
    <div className={`flex items-start gap-2 rounded-xl bg-oo-line-soft text-oo-ink-2 ${phone ? "px-3 py-2.5 text-[12.5px]" : "px-4 py-3 text-[14px]"}`}>
      <Info size={phone ? 14 : 16} className="mt-0.5 shrink-0" aria-hidden="true" />
      {REVIEW_NOTE}
    </div>
  );
}

function DesktopHero({ state }: { state: HeroState }) {
  return (
    <div className="absolute inset-0 bg-oo-paper font-sans text-oo-ink">
      <Nav />
      <div className="grid grid-cols-[560px_1fr] gap-20 px-24 pt-16">
        <HeroCopy />
        <div className="relative">
          <div className="absolute -left-12 top-0 w-[400px]">
            <Track annotated={state !== "load"} />
          </div>
          <div className="space-y-3 pt-[120px]">
            <ResultsCard state={state} />
            <ReviewNote />
          </div>
        </div>
      </div>
    </div>
  );
}

function PhoneHero() {
  return (
    <div className="absolute inset-0 space-y-5 bg-oo-paper px-5 py-5 font-sans text-oo-ink">
      <span className="flex items-center gap-2">
        <TrackMark size={22} />
        <Wordmark size={17} />
      </span>
      <HeroCopy phone />
      <ResultsCard state="flat" phone />
      <ReviewNote phone />
    </div>
  );
}

function GenomeHero({ beat }: { beat: "karyotype" | "bases" }) {
  return (
    <div className="absolute inset-0 bg-oo-paper font-sans text-oo-ink">
      <Nav />
      <div className="grid grid-cols-[560px_1fr] gap-20 px-24 pt-16">
        <HeroCopy />
        <div className="relative flex h-[560px] flex-col justify-center rounded-2xl border border-oo-line bg-oo-surface p-10">
          {beat === "karyotype" ? (
            <>
              <div className="flex h-[360px] items-end justify-center gap-[10px]">
                {CHROMOSOMES.map((h, i) => (
                  <span key={i} className={`w-[16px] rounded-full ${i === 11 ? "bg-oo-eosin" : "bg-oo-ink/75"}`} style={{ height: `${h}%` }} />
                ))}
              </div>
              <div className="mt-4 flex justify-between text-[13px] text-oo-muted">
                <span>Stylized karyotype · schematic, not to scale</span>
                <span className="font-mono">chr12 highlighted</span>
              </div>
            </>
          ) : (
            <>
              <div className="font-mono text-[30px] tracking-[0.1em]">
                {SEQUENCE.slice(0, 21)
                  .split("")
                  .map((b, i) => (
                    <span key={i} className={i === C34 ? "rounded bg-oo-eosin-tint px-1 font-semibold text-oo-ink underline decoration-oo-eosin decoration-[3px] underline-offset-[6px]" : "text-oo-ink-3"}>
                      {b}
                    </span>
                  ))}
              </div>
              <div className="mt-6 space-y-1 text-[14px] text-oo-ink-2">
                <div className="font-mono">c.34G&gt;T · p.Gly12Cys</div>
                <div className="text-oo-muted">Coding strand (cDNA), codons 9–15 · illustration, not a report field</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Frame({ n, at, caption, children }: { n: string; at: string; caption: string; children: React.ReactNode }) {
  return (
    <figure className="space-y-3">
      {children}
      <figcaption className="space-y-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[12px] font-semibold text-oo-hema">{n}</span>
          <span className="font-mono text-[12px] text-oo-muted">{at}</span>
        </div>
        <p className="text-[14px] leading-snug text-oo-ink-2">{caption}</p>
      </figcaption>
    </figure>
  );
}

function Verdict({ items }: { items: { label: string; text: string }[] }) {
  return (
    <div className="grid gap-3 rounded-xl border border-oo-line bg-oo-surface p-5 text-sm md:grid-cols-2">
      {items.map((it) => (
        <p key={it.label} className={it.label === "Call" ? "md:col-span-2" : undefined}>
          <span className={`font-semibold ${it.label === "Call" ? "text-oo-hema" : ""}`}>{it.label}.</span>{" "}
          <span className="text-oo-ink-2">{it.text}</span>
        </p>
      ))}
    </div>
  );
}

function ConceptHeader({ id, name, idea }: { id: string; name: string; idea: string }) {
  return (
    <div className="space-y-1">
      <h2 className="text-2xl font-semibold tracking-tight">
        <span className="text-oo-hema">{id}.</span> {name}
      </h2>
      <p className="max-w-3xl text-oo-ink-2">{idea}</p>
    </div>
  );
}

export default function HeroLabPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className={`${displayFont.variable} min-h-screen bg-[#F1EDE6] px-5 py-12 text-oo-ink md:px-12`}>
      <div className="mx-auto max-w-6xl space-y-20">
        <header className="space-y-3">
          <p className="font-mono text-xs uppercase tracking-[0.12em] text-oo-muted">Internal · not shipped</p>
          <h1 className="text-4xl font-semibold tracking-tight">Hero storyboards, round 2</h1>
          <p className="max-w-3xl leading-relaxed text-oo-ink-2">
            Every frame is drawn at real size (1440×900, or 390×844 for phones) and scaled to fit, so type and spacing are
            what visitors would see. Round 1 was critiqued; this version merges concepts 1 and 3 into one product-first hero.
            The labels, CTA and review note are present from the first frame.
          </p>
        </header>

        <section className="space-y-6">
          <ConceptHeader
            id="A"
            name="Product first, then unpacked (recommended)"
            idea="The finished, labelled Results card is visible at load, so the first frame already shows the product. Scrolling up to 150vh only adds depth: the card settles flat, the variant gets annotated, and each drug row opens to show its own evidence sources."
          />
          <div className="grid gap-8 md:grid-cols-2">
            <Frame n="A.1" at="On load · 0%" caption="Complete and labelled at first paint, so the card is the LCP element. It sits tilted back 12° at 92% scale. The headline reveals line by line, once. The track draws in once over 600ms.">
              <ScaledStage width={1440} height={900}>
                <DesktopHero state="load" />
              </ScaledStage>
            </Frame>
            <Frame n="A.2" at="Scroll threshold 30%" caption="The card settles to flat and full scale (transform only). The variant annotation fades in. A discrete state: scrolling back reverses it, with no replayed springs.">
              <ScaledStage width={1440} height={900}>
                <DesktopHero state="flat" />
              </ScaledStage>
            </Frame>
          </div>
          <div className="grid gap-8 md:grid-cols-[2fr_1fr]">
            <Frame n="A.3" at="Scroll threshold 65%" caption="Each row opens to show its approval status, its mechanism and its own named evidence sources. Osimertinib's thinner evidence and different indication are shown, not hidden. The sticky stage releases at 100% (150vh).">
              <ScaledStage width={1440} height={900}>
                <DesktopHero state="unpacked" />
              </ScaledStage>
            </Frame>
            <Frame n="A.4" at="Phone · and reduced motion" caption="No scroll scene. The flat, labelled composition renders at once. This is also what reduced-motion visitors get on desktop.">
              <ScaledStage width={390} height={844}>
                <PhoneHero />
              </ScaledStage>
            </Frame>
          </div>
          <Verdict
            items={[
              { label: "For", text: "The product is visible at frame 0, as on Mercury. Every element is real demo data, and there are three discrete states instead of a continuous chip choreography. Reduced motion and phones get the same frame, so there is no separate fallback design." },
              { label: "Against", text: "Less spectacular than a full assembly animation. The wow comes from the tilt settling and the rows unpacking, so polish matters." },
              { label: "Risk", text: "Low to medium. Transforms only; rank bars use scaleX; shadow is static. No layoutId scrubbing." },
              { label: "Effort", text: "About 2 days on top of the Results components, which are needed anyway." },
              { label: "Call", text: "Recommended. It answers the round-1 critique: product first, labels always visible, honest about Osimertinib." },
            ]}
          />
        </section>

        <section className="space-y-6">
          <ConceptHeader
            id="B"
            name="Genome to report"
            idea="A zoom from the whole genome down to one DNA letter, ending on the same card. Now shown with the real headline and CTA so it can be judged fairly."
          />
          <div className="grid gap-8 md:grid-cols-2">
            <Frame n="B.1" at="Scroll 0–30%" caption="The headline and CTA are fixed on the left. A stylized karyotype with chromosome 12 in eosin, the visualization highlight color.">
              <ScaledStage width={1440} height={900}>
                <GenomeHero beat="karyotype" />
              </ScaledStage>
            </Frame>
            <Frame n="B.2" at="Scroll 30–70%" caption="Base level on the coding strand: c.34 G>T in codon 12. Then the letter grows into the Results card from A.2.">
              <ScaledStage width={1440} height={900}>
                <GenomeHero beat="bases" />
              </ScaledStage>
            </Frame>
          </div>
          <Verdict
            items={[
              { label: "For", text: "Only a genomics product can make this move. Memorable." },
              { label: "Against", text: "The product doesn't appear until the last 30% of the scroll. Biology first, value last." },
              { label: "Risk", text: "High. A camera zoom across scales is the hardest thing to keep at 60fps. Strand and scale details invite expert nitpicks (KRAS is on the minus strand)." },
              { label: "Effort", text: "About 5–6 days." },
              { label: "Call", text: "Not the hero. Reuse the base-level frame in a later 'how it works' section." },
            ]}
          />
        </section>
      </div>
    </main>
  );
}

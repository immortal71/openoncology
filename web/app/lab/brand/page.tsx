import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { TrackMark, Wordmark } from "@/components/brand/marks";

export const metadata: Metadata = {
  title: "Brand lab | OpenOncology",
  robots: { index: false, follow: false },
};

const PAPER = "#FAF7F2";
const INK = "#16181D";
const INK_2 = "#3F3C37";
const MUTED = "#5E5A54";
const LINE = "#E8E1D6";
const DARK = "#111311";
const ON_DARK = "#EDEBE4";

const VARIANTS = [
  { id: "original", name: "A1 · Original", note: "Four parts. Reads as a sequence, but the dot gets lost at 16px." },
  { id: "bold", name: "A2 · Bold", note: "Three parts, heavier strokes. Built for favicons and small UI." },
  { id: "fine", name: "A3 · Fine", note: "Thinner track, taller spike. Elegant at large sizes, weak below 24px." },
] as const;

const ACCENTS = [
  { name: "Green", value: "#0F6E56", onDark: "#4FB58C" },
  { name: "Violet", value: "#3D2C8D", onDark: "#A99CF0" },
];

function Tile({ bg, label, children }: { bg: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border p-6" style={{ background: bg, borderColor: bg === DARK ? DARK : LINE }}>
      <div className="flex min-h-[88px] flex-wrap items-center gap-5">{children}</div>
      <span className="text-sm" style={{ color: bg === DARK ? "#A8AAA5" : MUTED }}>
        {label}
      </span>
    </div>
  );
}

export default function BrandLabPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="min-h-screen px-5 py-12 md:px-12" style={{ background: PAPER, color: INK }}>
      <div className="mx-auto max-w-6xl space-y-16">
        <header className="space-y-3">
          <p className="font-mono text-xs uppercase tracking-[0.12em]" style={{ color: MUTED }}>
            Internal · not shipped
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">Brand lab: Track</h1>
          <p className="max-w-2xl text-base leading-relaxed" style={{ color: INK_2 }}>
            Direction A won. Below are three refinements of the mark, then wordmarks where the l in Oncology becomes the
            raised variant block, so the mark and the name are one idea.
          </p>
        </header>

        <section className="space-y-6 border-t pt-10" style={{ borderColor: LINE }}>
          <h2 className="text-2xl font-semibold tracking-tight">Mark refinements</h2>
          <div className="grid gap-4 md:grid-cols-3">
            {VARIANTS.map((v) => (
              <div key={v.id} className="rounded-xl border bg-white p-6" style={{ borderColor: LINE }}>
                <TrackMark variant={v.id} size={120} ink={INK} accent={ACCENTS[0].value} title={`${v.name} mark`} />
                <div className="mt-6 flex items-end gap-4">
                  <TrackMark variant={v.id} size={32} ink={INK} accent={ACCENTS[0].value} />
                  <TrackMark variant={v.id} size={24} ink={INK} accent={ACCENTS[0].value} />
                  <TrackMark variant={v.id} size={16} ink={INK} accent={ACCENTS[0].value} />
                </div>
                <p className="mt-4 text-base font-semibold">{v.name}</p>
                <p className="mt-1 text-sm leading-relaxed" style={{ color: MUTED }}>
                  {v.note}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Tile bg={DARK} label="On dark, green and violet">
              {VARIANTS.map((v) => (
                <TrackMark key={v.id} variant={v.id} size={56} ink={ON_DARK} accent={ACCENTS[0].onDark} />
              ))}
              <TrackMark variant="bold" size={56} ink={ON_DARK} accent={ACCENTS[1].onDark} />
            </Tile>
            <Tile bg="#FFFFFF" label="App icons (A2 Bold)">
              <span className="grid h-16 w-16 place-items-center rounded-2xl" style={{ background: INK }}>
                <TrackMark variant="bold" size={42} ink={ON_DARK} accent={ACCENTS[0].onDark} />
              </span>
              <span className="grid h-16 w-16 place-items-center rounded-2xl" style={{ background: ACCENTS[0].value }}>
                <TrackMark variant="bold" size={42} ink="#FFFFFF" accent="#BDEBD7" />
              </span>
              <span className="grid h-16 w-16 place-items-center rounded-2xl" style={{ background: ACCENTS[1].value }}>
                <TrackMark variant="bold" size={42} ink="#FFFFFF" accent="#F2C4D6" />
              </span>
            </Tile>
            <Tile bg="#FFFFFF" label="Browser tab at 16px">
              {VARIANTS.map((v) => (
                <span
                  key={v.id}
                  className="flex items-center gap-2 rounded-t-lg border border-b-0 px-3 py-2 text-xs"
                  style={{ borderColor: LINE, background: "#F2EFEA", color: INK_2 }}
                >
                  <TrackMark variant={v.id} size={16} ink={INK} accent={ACCENTS[0].value} />
                  OpenOncology
                </span>
              ))}
            </Tile>
          </div>
        </section>

        <section className="space-y-6 border-t pt-10" style={{ borderColor: LINE }}>
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">Wordmarks: the l is the variant</h2>
            <p style={{ color: INK_2 }}>
              IBM Plex Sans Semibold, already bundled. The chosen version gets outlined to SVG paths and kerned by hand.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Tile bg="#FFFFFF" label="W1 · Sentence case, wordmark alone">
              <Wordmark size={44} ink={INK} accent={ACCENTS[0].value} />
            </Tile>
            <Tile bg={DARK} label="W1 · On dark">
              <Wordmark size={44} ink={ON_DARK} accent={ACCENTS[0].onDark} />
            </Tile>

            <Tile bg="#FFFFFF" label="W2 · Lowercase, weight split">
              <Wordmark size={44} ink={INK} accent={ACCENTS[0].value} lowercase split />
            </Tile>
            <Tile bg={DARK} label="W2 · On dark">
              <Wordmark size={44} ink={ON_DARK} accent={ACCENTS[0].onDark} lowercase split />
            </Tile>

            <Tile bg="#FFFFFF" label="W3 · Lockup: A2 mark + W1">
              <TrackMark variant="bold" size={40} ink={INK} accent={ACCENTS[0].value} />
              <Wordmark size={34} ink={INK} accent={ACCENTS[0].value} />
            </Tile>
            <Tile bg="#FFFFFF" label="W1 in violet, for comparison">
              <Wordmark size={44} ink={INK} accent={ACCENTS[1].value} />
            </Tile>
          </div>

          <Tile bg="#FFFFFF" label="In a nav bar at real size (16px wordmark, 22px mark)">
            <div className="flex w-full items-center justify-between rounded-lg border px-5 py-3" style={{ borderColor: LINE, background: PAPER }}>
              <span className="flex items-center gap-2">
                <TrackMark variant="bold" size={22} ink={INK} accent={ACCENTS[0].value} />
                <Wordmark size={17} ink={INK} accent={ACCENTS[0].value} />
              </span>
              <span className="flex gap-6 text-sm" style={{ color: INK_2 }}>
                <span>Product</span>
                <span>Docs</span>
                <span>Community</span>
              </span>
            </div>
          </Tile>
        </section>
      </div>
    </main>
  );
}

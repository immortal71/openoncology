"use client";

import { OptionA, OptionB, OptionC, type CardData } from "@/components/atlas/card-options";

const OPTIONS = [
  { id: "a", name: "Option A · Step run", ref: "Copied from Inngest's hero: status pills beside bracketed steps, a checking state that walks the steps once, then settles.", Comp: OptionA },
  { id: "b", name: "Option B · Record table", ref: "Copied from Attio's app window: window bar, view chip, a table whose state cells fill in one by one as tinted pills.", Comp: OptionB },
  { id: "c", name: "Option C · Command palette", ref: "Copied from Raycast's launcher: list with a moving selection, a detail pane with Information rows, an action footer. Hover to take over.", Comp: OptionC },
];

export function CardOptions({ data }: { data: CardData }) {
  return (
    <div className="mx-auto w-full max-w-[1280px] px-5 py-16 md:px-10">
      {OPTIONS.map(({ id, name, ref, Comp }) => {
        const [lab, clinic] = Comp({ d: data });
        return (
          <section key={id} id={`option-${id}`} className="border-b border-[#E2DEE6] py-14 first:pt-0 last:border-b-0">
            <p className="font-mono text-[12px] uppercase tracking-[0.06em] text-[#69518C]">{name}</p>
            <p className="mt-1.5 max-w-[80ch] text-[14px] text-[#625E68]">{ref}</p>
            <div className="mt-8 grid gap-6 md:grid-cols-2">
              <article className="min-w-0">
                <h3 className="text-[22px] font-semibold leading-[1.25] tracking-[-0.02em]">What your lab&apos;s next sequencing run should add.</h3>
                <p className="mt-2 max-w-[46ch] text-[15.5px] leading-[1.6] text-[#4A4652]">The same calls as step 1, with the fields this result doesn&apos;t carry left visibly empty.</p>
                {lab}
              </article>
              <article className="min-w-0">
                <h3 className="text-[22px] font-semibold leading-[1.25] tracking-[-0.02em]">What your hospital team checks before acting.</h3>
                <p className="mt-2 max-w-[46ch] text-[15.5px] leading-[1.6] text-[#4A4652]">Evidence that wasn&apos;t recorded or assessed, ending at the person who decides.</p>
                {clinic}
              </article>
            </div>
          </section>
        );
      })}
    </div>
  );
}

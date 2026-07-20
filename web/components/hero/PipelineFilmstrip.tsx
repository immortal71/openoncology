const STAGES = [
  {
    num: "01",
    tag: "VARIANT CALL",
    title: "Actionability Check",
    desc: "Validate clinical relevance in your cancer context. If not actionable, we state it directly.",
  },
  {
    num: "02",
    tag: "DRUG RANK",
    title: "Repurposed Options",
    desc: "Rank already-approved candidates first — lower cost, lower risk, faster decision.",
  },
  {
    num: "03",
    tag: "CUSTOM BRIEF",
    title: "Custom Discovery Brief",
    desc: "Structure prediction, docking, and lead ranking generated only when repurposing fails.",
  },
  {
    num: "04",
    tag: "SYNTHESIS",
    title: "Manufacture + Funding",
    desc: "Place a synthesis request and launch crowdfunding from the same case in one step.",
  },
];

export default function PipelineFilmstrip() {
  return (
    <div className="flex flex-col md:flex-row md:items-stretch">
      {STAGES.map((stage, i) => (
        <div key={stage.num} className="flex items-stretch flex-1">
          <div className="border-l-2 border-white/30 pl-4 pr-5 py-5 flex-1">
            <span className="font-mono text-neutral-heading text-xs tracking-widest">{stage.num}</span>
            <p className="font-mono text-[10px] text-neutral-muted tracking-widest mt-1 uppercase">
              {stage.tag}
            </p>
            <h3 className="text-neutral-heading font-semibold text-sm mt-2 mb-1.5">{stage.title}</h3>
            <p className="text-neutral-body text-sm leading-relaxed">{stage.desc}</p>
          </div>
          {i < STAGES.length - 1 && (
            <div className="hidden md:flex items-center px-2 text-neutral-muted select-none">→</div>
          )}
        </div>
      ))}
    </div>
  );
}

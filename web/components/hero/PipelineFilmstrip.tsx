const STAGES = [
  {
    num: "01",
    tag: "GENOMIC INPUT",
    title: "Supply findings",
    desc: "Start with genomic findings and cancer context. Lab integration remains in development.",
  },
  {
    num: "02",
    tag: "EVIDENCE LOOKUP",
    title: "Find drug evidence",
    desc: "Look up treatment evidence for the supplied findings and record gaps in the available information.",
  },
  {
    num: "03",
    tag: "EVIDENCE REPORT",
    title: "Review the shortlist",
    desc: "Read the ranked candidates with their evidence sources and limitations.",
  },
  {
    num: "04",
    tag: "CLINICIAN REVIEW",
    title: "Decide next steps",
    desc: "A qualified oncologist checks the evidence in the patient's clinical context.",
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

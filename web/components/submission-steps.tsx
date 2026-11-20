import { ink, line, muted } from "@/components/workspace/parts";

export function SubmissionSteps({ active }: { active: 0 | 1 | 2 }) {
  const steps = ["Upload", "Analysis", "Results"] as const;
  return (
    <ol aria-label="Submission progress" className="flex items-center gap-0">
      {steps.map((step, i) => (
        <li key={step} aria-current={i === active ? "step" : undefined} className="flex flex-1 items-center last:flex-none">
          <div className="flex items-center gap-1.5">
            <span
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-[12px] font-medium ${
                i < active ? "bg-[#EEE9F4] text-[#513C68]" : i === active ? "bg-[#69518C] text-white" : `border ${line} bg-white text-[#625E68]`
              }`}
            >
              {i + 1}
            </span>
            <span className={`text-[12.5px] font-medium ${i === active ? ink : muted}`}>{step}</span>
          </div>
          {i < steps.length - 1 ? <span aria-hidden="true" className={`mx-1 h-px sm:mx-3 flex-1 ${i < active ? "bg-[#69518C]" : "bg-[#E2DEE6]"}`} /> : null}
        </li>
      ))}
    </ol>
  );
}

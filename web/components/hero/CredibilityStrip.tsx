const METRICS = [
  { label: "Hit@3", value: "0.900" },
  { label: "False Positives", value: "0%" },
  { label: "License", value: "Open Source" },
];

export default function CredibilityStrip() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-white/10 border border-white/10">
      {METRICS.map((m) => (
        <div key={m.label} className="p-5 text-center sm:text-left">
          <p className="font-mono text-2xl font-bold text-neutral-heading">{m.value}</p>
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-muted mt-1.5">
            {m.label}
          </p>
        </div>
      ))}
    </div>
  );
}

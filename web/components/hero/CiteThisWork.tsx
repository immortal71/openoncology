const DOI = "10.21203/rs.3.rs-9707913/v1";
const PREPRINT_URL = "https://doi.org/10.21203/rs.3.rs-9707913/v1";

export default function CiteThisWork() {
  return (
    <div className="border border-white/10 bg-white/[0.02] p-6">
      <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-muted mb-3">
        Cite this work
      </p>
      <p className="text-sm text-neutral-body leading-relaxed italic">
        Kharel, A. <span className="not-italic">OpenOncology: An Open-Source Framework for
        Evidence-Based Drug Matching and De Novo Custom Drug Discovery in Precision
        Oncology.</span> Research Square (2026).
      </p>
      <p className="font-mono text-xs text-neutral-muted mt-3">
        DOI: {DOI} ·{" "}
        <a
          href={PREPRINT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-neutral-heading underline underline-offset-2 hover:text-white"
        >
          Read the preprint →
        </a>
      </p>
    </div>
  );
}

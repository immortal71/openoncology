"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { AlertCircle, ArrowLeft, Dna, Sparkles } from "lucide-react";
import { DEMO_ID } from "@/lib/demo-data";
import { api } from "@/lib/api";
import { normalizeStatus, STATUS_LABEL, type SubmissionStatus } from "@/lib/status";
import { atlasSans } from "@/lib/atlas-font";
import { focus, ink, line, muted, surface } from "@/components/workspace/parts";

const POLL_MS = 2500;
const MAX_POLLS = 24; // ~60s of unresolved status before we stop polling silently and say so
const DEMO_STEPS = ["Reading variant calls", "Matching evidence sources", "Ranking candidates"] as const;

function Rise({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </motion.div>
  );
}

function Steps() {
  const items = ["Upload", "Analysis", "Results"] as const;
  return (
    <ol className="flex items-center gap-0">
      {items.map((step, i) => (
        <li key={step} className="flex flex-1 items-center last:flex-none">
          <div className="flex flex-col items-center gap-1.5">
            <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-[12px] font-medium ${i <= 1 ? "bg-[#69518C] text-white" : `border ${line} bg-white text-[#625E68]`}`}>{i + 1}</span>
            <span className={`text-[12.5px] font-medium ${i === 1 ? ink : muted}`}>{step}</span>
          </div>
          {i < items.length - 1 ? <span aria-hidden="true" className={`mx-3 mb-5 h-px flex-1 ${i < 1 ? "bg-[#69518C]" : "bg-[#E2DEE6]"}`} /> : null}
        </li>
      ))}
    </ol>
  );
}

function Spinner() {
  return (
    <span aria-hidden="true" className="relative grid h-14 w-14 shrink-0 place-items-center">
      <span className="absolute inset-0 rounded-full border-2 border-[#E2DEE6]" />
      <span className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-[#69518C]" style={{ animationDuration: "900ms" }} />
      <Dna size={20} className="text-[#69518C]" />
    </span>
  );
}

function DemoAnalysis() {
  const router = useRouter();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (step >= DEMO_STEPS.length - 1) {
      const t = setTimeout(() => router.push(`/results/${DEMO_ID}?demo=true`), 650);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStep((s) => s + 1), 650);
    return () => clearTimeout(t);
  }, [step, router]);

  return (
    <Rise className={`rounded-[12px] border ${line} bg-white p-8 text-center ${surface}`}>
      <div className="mx-auto mb-5 flex justify-center">
        <Spinner />
      </div>
      <p className={`text-[12.5px] font-medium uppercase tracking-[0.06em] ${muted}`}>Illustrative · demo case</p>
      <h1 className={`mt-2 text-[22px] font-semibold ${ink}`} aria-live="polite">
        {DEMO_STEPS[step]}…
      </h1>
      <p className={`mt-2 text-[14px] leading-[21px] ${muted}`}>No files were analyzed — this walks through the demo case already built into the Evidence Atlas.</p>
    </Rise>
  );
}

function RealAnalysis({ id }: { id: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<SubmissionStatus>("queued");
  const [failMsg, setFailMsg] = useState<string | null>(null);
  const [stalled, setStalled] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attempts = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await api.getResults(id);
        if (cancelled) return;
        const s = normalizeStatus(res.status);
        setStatus(s);
        if (s === "complete") {
          router.push(`/results/${id}`);
          return;
        }
        if (s === "failed") {
          setFailMsg(res.message ?? "Analysis failed. Check the file formats and try again.");
          return;
        }
        attempts.current += 1;
        if (attempts.current >= MAX_POLLS) {
          setStalled(true);
          return;
        }
        timer.current = setTimeout(poll, POLL_MS);
      } catch (err) {
        if (cancelled) return;
        setStatus("failed");
        setFailMsg(err instanceof Error ? err.message : "Could not reach the analysis service.");
      }
    };
    poll();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id, router, retryKey]);

  const retry = () => {
    attempts.current = 0;
    setStalled(false);
    setRetryKey((k) => k + 1);
  };

  if (status === "failed") {
    return (
      <Rise className={`rounded-[12px] border border-[#D9B8AE] bg-[#FBF1EE] p-8 text-center`}>
        <AlertCircle size={36} aria-hidden="true" className="mx-auto mb-3 text-[#9E4A3A]" />
        <h1 className="text-[20px] font-semibold text-[#7A3326]">Analysis failed</h1>
        <p className="mt-2 text-[14px] leading-[21px] text-[#9E4A3A]">{failMsg}</p>
        <Link href="/submit" className={`mt-5 inline-flex items-center gap-1.5 text-[14px] font-medium text-[#69518C] underline-offset-4 hover:underline ${focus}`}>
          <ArrowLeft size={15} aria-hidden="true" /> Back to submit
        </Link>
      </Rise>
    );
  }

  if (stalled) {
    return (
      <Rise className={`rounded-[12px] border border-[#E6D3AE] bg-[#FBF4E6] p-8 text-center`}>
        <AlertCircle size={36} aria-hidden="true" className="mx-auto mb-3 text-[#7A4F14]" />
        <h1 className="text-[20px] font-semibold text-[#7A4F14]">Still {STATUS_LABEL[status].toLowerCase()}</h1>
        <p className="mt-2 text-[14px] leading-[21px] text-[#7A4F14]">
          This is taking longer than the usual few minutes. The submission hasn&apos;t failed — it&apos;s still showing &quot;{STATUS_LABEL[status]}&quot; after a minute of checking. You can keep
          waiting or check again later.
        </p>
        <button type="button" onClick={retry} className={`mt-5 inline-flex items-center gap-1.5 text-[14px] font-medium text-[#69518C] underline-offset-4 hover:underline ${focus}`}>
          Check again
        </button>
      </Rise>
    );
  }

  return (
    <Rise className={`rounded-[12px] border ${line} bg-white p-8 text-center ${surface}`}>
      <div className="mx-auto mb-5 flex justify-center">
        <Spinner />
      </div>
      <p className={`text-[12.5px] font-medium uppercase tracking-[0.06em] ${muted}`} aria-live="polite">
        {STATUS_LABEL[status]}
      </p>
      <h1 className={`mt-2 text-[22px] font-semibold ${ink}`}>Analyzing your sample…</h1>
      <p className={`mt-2 text-[14px] leading-[21px] ${muted}`}>
        Initial mutation check and repurposed-drug triage usually appear in minutes. This page checks status every few seconds — you can safely close it and come back.
      </p>
      <p className={`mt-5 rounded-[8px] border ${line} bg-[#FAF9F7] p-3 font-mono text-[12.5px] ${muted}`}>Submission ID: {id}</p>
    </Rise>
  );
}

function AnalysisInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  const isDemo = searchParams.get("demo") === "true";

  return (
    <main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] font-[family-name:var(--font-atlas)] ${ink}`}>
      <div className="mx-auto max-w-[640px] px-6 py-10">
        <Steps />
        <div className="mt-8">
          {isDemo ? (
            <DemoAnalysis />
          ) : id ? (
            <RealAnalysis id={id} />
          ) : (
            <Rise className={`rounded-[12px] border ${line} bg-white p-8 text-center ${surface}`}>
              <Sparkles size={32} aria-hidden="true" className="mx-auto mb-3 text-[#69518C]" />
              <h1 className={`text-[20px] font-semibold ${ink}`}>No submission to analyze</h1>
              <p className={`mt-2 text-[14px] leading-[21px] ${muted}`}>Submit a sample first, or try the demo case from there.</p>
              <Link href="/submit" className={`mt-5 inline-flex items-center gap-1.5 text-[14px] font-medium text-[#69518C] underline-offset-4 hover:underline ${focus}`}>
                <ArrowLeft size={15} aria-hidden="true" /> Back to submit
              </Link>
            </Rise>
          )}
        </div>
      </div>
    </main>
  );
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={null}>
      <AnalysisInner />
    </Suspense>
  );
}

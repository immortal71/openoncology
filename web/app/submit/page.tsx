"use client";
import { Suspense } from "react";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams, useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Upload, FileText, Dna, CheckCircle, AlertCircle, FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { atlasSans } from "@/lib/atlas-font";
import { focus, ink, line, muted, surface } from "@/components/workspace/parts";

const schema = z.object({
  cancer_type: z.string().min(2, "Please specify the cancer type").max(128),
  biopsy_file: z
    .instanceof(File)
    .refine((f) => f.size <= 50 * 1024 * 1024, "Biopsy file must be under 50MB")
    .refine((f) => {
      const allowedExt = ["pdf", "jpg", "jpeg", "png", "txt", "doc", "docx", "rtf", "xml", "json"];
      const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
      return allowedExt.includes(ext);
    }, "Biopsy file must be PDF, image, text, document, or XML/JSON"),
  dna_file: z
    .instanceof(File)
    .refine((f) => f.size <= 500 * 1024 * 1024, "DNA file must be under 500MB")
    .refine((f) => {
      const allowedExt = ["vcf", "fastq", "fq", "bam", "gz", "txt", "csv", "tsv", "xml", "json"];
      const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
      return allowedExt.includes(ext);
    }, "DNA file must be genomic or structured data format (VCF/FASTQ/BAM/GZ/TXT/CSV/TSV/XML/JSON)"),
});

type FormData = z.infer<typeof schema>;

const primaryBtn = `inline-flex h-12 w-full items-center justify-center gap-2 rounded-[8px] bg-[#25202F] px-6 text-[15px] font-medium text-[#F7F5F0] transition-[background-color,transform] duration-150 hover:bg-[#3A3446] active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 ${focus}`;
const cardField = `w-full rounded-[8px] border ${line} bg-white px-4 py-3 text-[14px] ${ink} placeholder:text-[#625E68] transition-colors duration-150 focus:border-[#69518C] focus:outline-none ${focus}`;

function Rise({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </motion.div>
  );
}

function Steps({ active }: { active: 0 | 1 | 2 }) {
  const steps = ["Upload", "Analysis", "Results"] as const;
  return (
    <ol className="flex items-center gap-0">
      {steps.map((step, i) => (
        <li key={step} className="flex flex-1 items-center last:flex-none">
          <div className="flex flex-col items-center gap-1.5">
            <span
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-[12px] font-medium ${
                i < active ? "bg-[#69518C] text-white" : i === active ? "bg-[#69518C] text-white" : `border ${line} bg-white text-[#625E68]`
              }`}
            >
              {i + 1}
            </span>
            <span className={`text-[12.5px] font-medium ${i === active ? ink : muted}`}>{step}</span>
          </div>
          {i < steps.length - 1 ? <span aria-hidden="true" className={`mx-3 mb-5 h-px flex-1 ${i < active ? "bg-[#69518C]" : "bg-[#E2DEE6]"}`} /> : null}
        </li>
      ))}
    </ol>
  );
}

function Dropzone({ label: title, hint, icon: Icon, file, accept, onFile, error, accessibleName }: { label: string; hint: string; icon: typeof FileText; file?: File; accept: string; onFile: (f: File) => void; error?: string; accessibleName: string }) {
  const id = useId();
  return (
    <div>
      <p id={`${id}-title`} className={`mb-1.5 block text-[13px] font-medium ${ink}`}>
        {title}
      </p>
      <label
        htmlFor={id}
        className={`group flex h-36 w-full cursor-pointer flex-col items-center justify-center rounded-[10px] border border-dashed ${
          error ? "border-[#C9776A]" : "border-[#B5B0BA] hover:border-[#69518C]"
        } bg-[#FAF9F7] transition-colors duration-150 hover:bg-[#F6F5F8] focus-within:border-[#69518C] focus-within:ring-2 focus-within:ring-[#69518C] focus-within:ring-offset-2`}
      >
        <span className="mb-2 grid h-10 w-10 place-items-center rounded-[8px] bg-[#ECEAEF] transition-colors duration-150 group-hover:bg-[#EEE8F5]">
          <Icon size={20} aria-hidden="true" className="text-[#69518C]" />
        </span>
        <span className={`px-3 text-center text-[13.5px] font-medium ${ink}`}>{file ? file.name : "Click or drag to upload"}</span>
        {!file ? <span className={`mt-1 text-[12px] ${muted}`}>{hint}</span> : null}
        <input
          id={id}
          type="file"
          accept={accept}
          className="sr-only"
          aria-labelledby={`${id}-title`}
          aria-label={accessibleName}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
      </label>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-[12.5px] text-[#9E4A3A]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function SubmitPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const isDemo = searchParams.get("demo") === "true";
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const biopsyFile = watch("biopsy_file");
  const dnaFile = watch("dna_file");

  const onSubmit = async (data: FormData) => {
    setStatus("uploading");
    setErrorMsg("");

    try {
      const form = new FormData();
      form.append("biopsy_file", data.biopsy_file);
      form.append("dna_file", data.dna_file);
      form.append("cancer_type", data.cancer_type);

      const result = await api.submitSample(form);
      setSubmissionId(result.submission_id);
      setStatus("success");
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Upload failed. Please try again.");
    }
  };

  if (status === "success") {
    return (
      <main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] font-[family-name:var(--font-atlas)] ${ink}`}>
        <div className="flex min-h-screen items-center justify-center p-6">
          <Rise className={`w-full max-w-md rounded-[12px] border ${line} bg-white p-8 text-center ${surface}`}>
            <CheckCircle className="mx-auto mb-4 text-[#4F7D5A]" size={48} aria-hidden="true" />
            <h2 className={`text-[22px] font-semibold ${ink}`}>Sample submitted.</h2>
            <p className={`mt-2 text-[14px] leading-[21px] ${muted}`}>
              Initial mutation check and repurposed-drug triage usually appear in minutes for VCF/document uploads. Full deep analysis (especially raw FASTQ/BAM pipelines) can take several
              hours, depending on file size and compute queue.
            </p>
            <p className={`mt-5 rounded-[8px] border ${line} bg-[#FAF9F7] p-3 font-mono text-[12.5px] ${muted}`}>Submission ID: {submissionId}</p>
            <Link href={`/submit/analysis?id=${submissionId}`} className={`${primaryBtn} mt-5`}>
              Track status <Upload size={16} aria-hidden="true" />
            </Link>
          </Rise>
        </div>
      </main>
    );
  }

  return (
    <main className={`${atlasSans.variable} min-h-screen bg-[#F7F5F0] font-[family-name:var(--font-atlas)] ${ink}`}>
      <div className="mx-auto max-w-[640px] px-6 py-10">
        <Steps active={0} />

        <div className={`mt-8 rounded-[12px] border ${line} bg-white p-7 md:p-9 ${surface}`}>
          <Rise>
            <h1 className="text-balance text-[28px] font-semibold leading-[1.15] tracking-[-0.03em]">Submit your sample.</h1>
            <p className={`mt-2 text-[15px] leading-[22px] ${muted}`}>
              Upload your case files to start the mutation pathway: actionable check, repurposed-drug search, custom-drug brief generation, and funding support when needed.
            </p>
          </Rise>

          <AnimatePresence>
            <Rise className={`mt-6 flex flex-col gap-3 rounded-[10px] border ${line} bg-[#FAF9F7] p-4 sm:flex-row sm:items-center`}>
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[8px] bg-[#EEE8F5]">
                <FlaskConical size={18} aria-hidden="true" className="text-[#69518C]" />
              </span>
              <div className="flex-1">
                <p className={`text-[14px] font-semibold ${ink}`}>Try a live demo</p>
                <p className={`mt-0.5 text-[13px] leading-[19px] ${muted}`}>See a full KRAS G12C · Non-Small Cell Lung Cancer case — Sotorasib ranked #1 (OncoKB Level 1).</p>
              </div>
              <button
                type="button"
                onClick={() => router.push(`/submit/analysis?demo=true`)}
                className={`inline-flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-[8px] border ${line} bg-white px-4 text-[13.5px] font-medium ${ink} transition-colors duration-150 hover:bg-[#F6F5F8] ${focus}`}
              >
                View demo results <Upload size={14} aria-hidden="true" className="rotate-90" />
              </button>
            </Rise>
          </AnimatePresence>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-6">
            <div>
              <label className={`mb-1.5 block text-[13px] font-medium ${ink}`}>Cancer type</label>
              <input {...register("cancer_type")} placeholder="e.g. Lung adenocarcinoma, Breast cancer, Glioblastoma" className={cardField} />
              {errors.cancer_type ? <p className="mt-1 text-[12.5px] text-[#9E4A3A]">{errors.cancer_type.message}</p> : null}
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <Dropzone label="Biopsy report · max 50 MB" hint="PDF · JPG · TXT · DOC" icon={FileText} file={biopsyFile} accept=".pdf,.jpg,.jpeg,.png,.txt,.doc,.docx,.rtf,.xml,.json" onFile={(f) => setValue("biopsy_file", f)} error={errors.biopsy_file?.message as string} accessibleName="Biopsy report file" />
              <Dropzone label="DNA / genomic file · max 500 MB" hint="VCF · FASTQ · BAM · GZ" icon={Dna} file={dnaFile} accept=".vcf,.fastq,.bam,.gz,.fq,.txt,.csv,.tsv,.xml,.json" onFile={(f) => setValue("dna_file", f)} error={errors.dna_file?.message as string} accessibleName="DNA or genomic file" />
            </div>

            <p className={`text-[12.5px] leading-[19px] ${muted}`}>
              By submitting, you consent to OpenOncology storing your files encrypted for analysis purposes. You can delete your data at any time from your dashboard. We never share
              identifiable data without your explicit consent.
            </p>

            <p className={`rounded-[8px] border ${line} bg-[#FAF9F7] p-3 text-[12.5px] leading-[19px] ${muted}`}>
              If Keycloak login is unavailable in your local environment, the app now supports a local demo-auth fallback so you can still test submissions.
            </p>

            {status === "error" ? (
              <div className="flex items-center gap-2 rounded-[8px] border border-[#D9B8AE] bg-[#FBF1EE] p-4">
                <AlertCircle size={18} aria-hidden="true" className="shrink-0 text-[#9E4A3A]" />
                <p className="text-[13.5px] text-[#9E4A3A]">{errorMsg}</p>
              </div>
            ) : null}

            <button type="submit" disabled={status === "uploading"} className={primaryBtn}>
              <Upload size={17} aria-hidden="true" />
              {status === "uploading" ? "Uploading & encrypting..." : "Submit sample"}
            </button>
          </form>
        </div>

        {isDemo ? (
          <p className={`mt-4 text-center text-[12.5px] ${muted}`}>
            Arrived from early access?{" "}
            <button type="button" onClick={() => router.push(`/submit/analysis?demo=true`)} className="font-medium text-[#69518C] underline-offset-4 hover:underline">
              Skip straight to the demo case
            </button>
            .
          </p>
        ) : null}
      </div>
    </main>
  );
}

export default function SubmitPage() {
  return (
    <Suspense fallback={null}>
      <SubmitPageInner />
    </Suspense>
  );
}

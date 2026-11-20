"use client";

import { useId, useState } from "react";
import { SubmissionSteps } from "@/components/submission-steps";
import { useForm } from "react-hook-form";

import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { Upload, FileText, Dna, CheckCircle, AlertCircle } from "lucide-react";
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

function Dropzone({ label: title, limit, hint, icon: Icon, file, accept, onFile, error, accessibleName }: { label: string; limit: string; hint: string; icon: typeof FileText; file?: File; accept: string; onFile: (f: File) => void; error?: string; accessibleName: string }) {
  const id = useId();
  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-3">
        <Icon size={18} aria-hidden="true" className="shrink-0 text-[#69518C]" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{title}</p>
          <p id={`${id}-hint`} className={`text-xs leading-5 ${muted}`}>{hint} · {limit}</p>
          {file && <p className="break-all text-sm text-[#513C68]" aria-live="polite">{file.name}</p>}
        </div>
        <label htmlFor={id} className="relative inline-flex min-h-10 shrink-0 cursor-pointer items-center rounded-lg border border-[#D6D0DB] bg-white px-3 text-sm font-medium hover:bg-[#F6F3F8] focus-within:ring-2 focus-within:ring-[#69518C]">
          {file ? "Replace" : "Choose file"}
        <input
          id={id}
          type="file"
          accept={accept}
          className="sr-only"
          aria-required="true"
          aria-label={accessibleName}
          aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-hint ${id}-error` : `${id}-hint`}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
      </label>
      </div>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-[12.5px] text-[#9E4A3A]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default function SubmitPage() {
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
      <div className="mx-auto max-w-[800px] px-4 py-5 sm:px-6">
        <SubmissionSteps active={0} />

        <div className={`mt-5 overflow-hidden rounded-[24px] border ${line} bg-white shadow-[0_12px_40px_-24px_rgba(44,34,55,0.28)]`}>
          <Rise className="border-b border-[#E5E0E7] bg-[#F6F3F8] px-5 py-5 sm:px-8 sm:py-6">
            <h1 className="text-balance text-[30px] sm:text-[36px] font-semibold leading-[1.15] tracking-[-0.03em]">Submit case files</h1>
            <p className={`mt-2 text-[15px] leading-[22px] ${muted}`}>
              Enter the cancer type and attach both files to start analysis.
            </p>
          </Rise>



          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 p-5 sm:p-8">
            <div>
              <label htmlFor="cancer-type" className={`mb-1.5 block text-[13px] font-medium ${ink}`}>Cancer type</label>
              <input id="cancer-type" {...register("cancer_type")} placeholder="e.g. Lung adenocarcinoma" className={cardField} />
              {errors.cancer_type ? <p className="mt-1 text-[12.5px] text-[#9E4A3A]">{errors.cancer_type.message}</p> : null}
            </div>

            <fieldset className="min-w-0"><legend className="mb-2 text-sm font-medium">Required case files</legend><div className="divide-y divide-[#E4DFE7] rounded-[14px] border border-[#DBD7DE] bg-[#FBFAF8]">
              <Dropzone label="Biopsy report" limit="Max 50 MB" hint="PDF · JPG · TXT · DOC" icon={FileText} file={biopsyFile} accept=".pdf,.jpg,.jpeg,.png,.txt,.doc,.docx,.rtf,.xml,.json" onFile={(f) => setValue("biopsy_file", f, { shouldValidate: true })} error={errors.biopsy_file?.message as string} accessibleName="Biopsy report file" />
              <Dropzone label="Genomic file" limit="Max 500 MB" hint="VCF · FASTQ · BAM" icon={Dna} file={dnaFile} accept=".vcf,.fastq,.bam,.gz,.fq,.txt,.csv,.tsv,.xml,.json" onFile={(f) => setValue("dna_file", f, { shouldValidate: true })} error={errors.dna_file?.message as string} accessibleName="DNA or genomic file" />
            </div>
              <details className="mt-2 text-xs text-[#625E68]">
                <summary className="w-fit cursor-pointer rounded py-1 text-[#513C68] focus-visible:outline-2">Supported formats</summary>
                <p className="mt-1">Biopsy report: PDF, JPG, JPEG, PNG, TXT, DOC, DOCX, RTF, XML or JSON.</p>
                <p className="mt-1">Genomic file: VCF, FASTQ, FQ, BAM, TXT, CSV, TSV, XML or JSON. The uploader also accepts gzip-compressed genomic files (.gz).</p>
              </details>
            </fieldset>

            <p className={`text-[12.5px] leading-[19px] ${muted}`}>
              By submitting, you consent to OpenOncology storing your files encrypted for analysis purposes. You can delete your data at any time from your dashboard. We never share
              identifiable data without your explicit consent.
            </p>



            {status === "error" ? (
              <div className="flex items-center gap-2 rounded-[8px] border border-[#D9B8AE] bg-[#FBF1EE] p-4">
                <AlertCircle size={18} aria-hidden="true" className="shrink-0 text-[#9E4A3A]" />
                <p className="text-[13.5px] text-[#9E4A3A]">{errorMsg}</p>
              </div>
            ) : null}

            <button type="submit" disabled={status === "uploading"} className={`${primaryBtn} sm:ml-auto sm:flex sm:w-auto`}>
              <Upload size={17} aria-hidden="true" />
              {status === "uploading" ? "Uploading & encrypting..." : "Submit sample"}
            </button>
          </form>
        </div>

      </div>
    </main>
  );
}

"use client";
import { Suspense } from "react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams, useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, Dna, CheckCircle, AlertCircle, FlaskConical } from "lucide-react";
import { api } from "@/lib/api";
import { DEMO_ID } from "@/lib/demo-data";

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
      <main className="min-h-screen flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="clinical-surface p-10 max-w-md w-full text-center shadow-xl shadow-cyan-900/10"
        >
          <CheckCircle className="text-green-500 mx-auto mb-4" size={56} />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Sample submitted!</h2>
          <p className="text-gray-600 text-sm mb-6">
            Initial mutation check and repurposed-drug triage usually appear in minutes for
            VCF/document uploads. Full deep analysis (especially raw FASTQ/BAM pipelines) can
            take several hours, depending on file size and compute queue.
          </p>
          <p className="bg-gray-50 rounded-lg p-3 font-mono text-xs text-gray-500 mb-6">
            Submission ID: {submissionId}
          </p>
          <a
            href={`/results/${submissionId}`}
            className="block w-full bg-cyan-700 text-white py-3 rounded-xl font-semibold hover:bg-cyan-600 transition-colors"
          >
            Track Status
          </a>
        </motion.div>
      </main>
    );
  }

  return (
    <main className="min-h-screen py-10 px-6">
      <div className="max-w-2xl mx-auto">
        {/* 3-step progress indicator */}
        <div className="flex items-center gap-0 mb-8">
          {["Upload", "Analysis", "Results"].map((step, i) => (
            <div key={step} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                  i === 0 ? "border-cyan-600 bg-cyan-600 text-white" : "border-slate-300 dark:border-slate-600 text-slate-400"
                }`}>
                  {i + 1}
                </div>
                <span className={`text-xs mt-1 font-medium ${
                  i === 0 ? "text-cyan-600" : "text-slate-400"
                }`}>{step}</span>
              </div>
              {i < 2 && (
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-700 mx-2 mb-4" />
              )}
            </div>
          ))}
        </div>

        <div className="clinical-surface p-7 md:p-9">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="text-3xl font-[var(--font-manrope)] font-extrabold text-slate-900 dark:text-slate-100 mb-2">Submit Your Sample</h1>
            <p className="text-slate-600 dark:text-slate-400 mb-5">
              Upload your case files to start the mutation pathway: actionable check,
              repurposed-drug search, custom-drug brief generation, and funding support when needed.
            </p>
          </motion.div>

        {/* Demo banner */}
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 rounded-r-xl border border-slate-700/60 bg-slate-800/50 p-4 flex flex-col sm:flex-row sm:items-center gap-3"
            style={{ borderLeft: '4px solid rgb(6 182 212)' }}
          >
            <FlaskConical className="shrink-0 text-cyan-400" size={20} />
            <div className="flex-1">
              <p className="text-sm font-semibold text-white">Try a live demo</p>
              <p className="text-xs text-slate-400 mt-0.5">
                See a full KRAS G12C · Non-Small Cell Lung Cancer case — Sotorasib ranked #1 (OncoKB Level 1).
              </p>
            </div>
            <button
              type="button"
              onClick={() => router.push(`/results/${DEMO_ID}?demo=true`)}
              className="shrink-0 rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-600 active:bg-cyan-800 transition-colors font-mono"
            >
              View demo results →
            </button>
          </motion.div>
        </AnimatePresence>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-7">
          {/* Cancer Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Cancer type
            </label>
            <input
              {...register("cancer_type")}
              placeholder="e.g. Lung adenocarcinoma, Breast cancer, Glioblastoma"
              className="w-full border border-slate-700 bg-slate-800/50 text-slate-100 rounded-xl px-4 py-3 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 focus:shadow-[0_0_0_3px_rgba(6,182,212,0.15)] transition-all"
            />
            {errors.cancer_type && (
              <p className="text-red-500 text-xs mt-1">{errors.cancer_type.message}</p>
            )}
          </div>

{/* File uploads — side-by-side on desktop */}
          <div className="grid md:grid-cols-2 gap-5">
            {/* Biopsy File */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Biopsy report
                <span className="ml-1.5 text-xs font-normal text-slate-400">max 50 MB</span>
              </label>
              <label className="group flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl cursor-pointer hover:border-cyan-500 dark:hover:border-cyan-500 hover:bg-cyan-50/30 dark:hover:bg-cyan-950/20 transition-all bg-slate-50/50 dark:bg-slate-800/30">
                <div className="mb-2 rounded-xl bg-cyan-50 dark:bg-cyan-950/50 p-2.5 group-hover:bg-cyan-100 dark:group-hover:bg-cyan-900/50 transition-colors">
                  <FileText className="text-cyan-600 dark:text-cyan-400" size={26} />
                </div>
                <span className="text-sm font-medium text-slate-600 dark:text-slate-300 text-center px-3">
                  {biopsyFile ? biopsyFile.name : "Click or drag to upload"}
                </span>
                {!biopsyFile && (
                  <span className="text-xs text-slate-400 mt-1">PDF · JPG · TXT · DOC</span>
                )}
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.txt,.doc,.docx,.rtf,.xml,.json"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && setValue("biopsy_file", e.target.files[0])}
                />
              </label>
              {errors.biopsy_file && (
                <p className="text-red-500 text-xs mt-1">{errors.biopsy_file.message as string}</p>
              )}
            </div>

            {/* DNA File */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                DNA / genomic file
                <span className="ml-1.5 text-xs font-normal text-slate-400">max 500 MB</span>
              </label>
              <label className="group flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl cursor-pointer hover:border-cyan-500 dark:hover:border-cyan-500 hover:bg-cyan-50/30 dark:hover:bg-cyan-950/20 transition-all bg-slate-50/50 dark:bg-slate-800/30">
                <div className="mb-2 rounded-xl bg-cyan-50 dark:bg-cyan-950/50 p-2.5 group-hover:bg-cyan-100 dark:group-hover:bg-cyan-900/50 transition-colors">
                  <Dna className="text-cyan-600 dark:text-cyan-400" size={26} />
                </div>
                <span className="text-sm font-medium text-slate-600 dark:text-slate-300 text-center px-3">
                  {dnaFile ? dnaFile.name : "Click or drag to upload"}
                </span>
                {!dnaFile && (
                  <div className="flex gap-1.5 mt-2 flex-wrap justify-center">
                    {["VCF", "FASTQ", "BAM", "GZ"].map((ext) => (
                      <span key={ext} className="font-mono text-[10px] font-bold bg-slate-700 text-cyan-300 px-1.5 py-0.5 rounded border border-slate-600">{ext}</span>
                    ))}
                  </div>
                )}
                <input
                  type="file"
                  accept=".vcf,.fastq,.bam,.gz,.fq,.txt,.csv,.tsv,.xml,.json"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && setValue("dna_file", e.target.files[0])}
                />
              </label>
              {errors.dna_file && (
                <p className="text-red-500 text-xs mt-1">{errors.dna_file.message as string}</p>
              )}
            </div>
          </div>

          {/* Consent notice */}
          <p className="text-xs text-slate-500 leading-relaxed">
            By submitting, you consent to OpenOncology storing your files encrypted for
            analysis purposes. You can delete your data at any time from your dashboard.
            We never share identifiable data without your explicit consent.
          </p>

          <p className="text-xs text-cyan-800 leading-relaxed bg-cyan-50 border border-cyan-100 rounded-lg p-3">
            If Keycloak login is unavailable in your local environment, the app now supports a local demo-auth fallback so you can still test submissions.
          </p>

          {status === "error" && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl p-4">
              <AlertCircle className="text-red-500 shrink-0" size={18} />
              <p className="text-red-600 text-sm">{errorMsg}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={status === "uploading"}
            className="w-full bg-cyan-700 text-white py-3.5 rounded-xl text-base font-bold hover:bg-cyan-600 active:bg-cyan-800 hover:shadow-lg hover:shadow-cyan-900/30 shadow-md shadow-cyan-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            <Upload size={18} />
            {status === "uploading" ? "Uploading & encrypting..." : "Submit Sample"}
          </button>
        </form>
        </div>
      </div>
    </main>
  );
}

export default function SubmitPage() {
  return <Suspense fallback={null}><SubmitPageInner /></Suspense>;
}

"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import { Upload, FileText, Dna, CheckCircle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

const schema = z.object({
  cancer_type: z.string().min(2, "Please specify the cancer type").max(128),
  biopsy_file: z
    .instanceof(File)
    .refine((f) => f.size <= 50 * 1024 * 1024, "Biopsy file must be under 50MB")
    .refine(
      (f) => ["application/pdf", "image/jpeg", "image/png"].includes(f.type),
      "Only PDF, JPG, or PNG files are accepted for biopsy"
    ),
  dna_file: z
    .instanceof(File)
    .refine((f) => f.size <= 500 * 1024 * 1024, "DNA file must be under 500MB"),
});

type FormData = z.infer<typeof schema>;

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
      <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-white rounded-2xl p-10 max-w-md w-full text-center shadow-lg"
        >
          <CheckCircle className="text-green-500 mx-auto mb-4" size={56} />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Sample submitted!</h2>
          <p className="text-gray-600 text-sm mb-6">
            Your sample is being processed. This usually takes 12–24 hours.
            We'll send you an email when your results are ready.
          </p>
          <p className="bg-gray-50 rounded-lg p-3 font-mono text-xs text-gray-500 mb-6">
            Submission ID: {submissionId}
          </p>
          <a
            href={`/results/${submissionId}`}
            className="block w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors"
          >
            Track Status
          </a>
        </motion.div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-16 px-6">
      <div className="max-w-2xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Submit Your Sample</h1>
          <p className="text-gray-500 mb-8">
            Upload your biopsy report and DNA file. Your data is encrypted immediately
            and never shared without your consent.
          </p>
        </motion.div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Cancer Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Cancer type
            </label>
            <input
              {...register("cancer_type")}
              placeholder="e.g. Lung adenocarcinoma, Breast cancer, Glioblastoma"
              className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {errors.cancer_type && (
              <p className="text-red-500 text-xs mt-1">{errors.cancer_type.message}</p>
            )}
          </div>

          {/* Biopsy File */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Biopsy report <span className="text-gray-400">(PDF, JPG, PNG — max 50MB)</span>
            </label>
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-200 rounded-xl cursor-pointer hover:border-blue-400 transition-colors">
              <FileText className="text-gray-400 mb-2" size={24} />
              <span className="text-sm text-gray-500">
                {biopsyFile ? biopsyFile.name : "Click to upload biopsy file"}
              </span>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
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
            <label className="block text-sm font-medium text-gray-700 mb-1">
              DNA file <span className="text-gray-400">(VCF, FASTQ, BAM, or .gz — max 500MB)</span>
            </label>
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-200 rounded-xl cursor-pointer hover:border-blue-400 transition-colors">
              <Dna className="text-gray-400 mb-2" size={24} />
              <span className="text-sm text-gray-500">
                {dnaFile ? dnaFile.name : "Click to upload DNA file"}
              </span>
              <input
                type="file"
                accept=".vcf,.fastq,.bam,.gz,.fq"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && setValue("dna_file", e.target.files[0])}
              />
            </label>
            {errors.dna_file && (
              <p className="text-red-500 text-xs mt-1">{errors.dna_file.message as string}</p>
            )}
          </div>

          {/* Consent notice */}
          <p className="text-xs text-gray-400 leading-relaxed">
            By submitting, you consent to OpenOncology storing your files encrypted for
            analysis purposes. You can delete your data at any time from your dashboard.
            We never share identifiable data without your explicit consent.
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
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            <Upload size={18} />
            {status === "uploading" ? "Uploading & encrypting..." : "Submit Sample"}
          </button>
        </form>
      </div>
    </main>
  );
}

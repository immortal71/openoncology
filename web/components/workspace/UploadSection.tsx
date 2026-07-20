"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FileUp, FileCheck2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

const INK = "#16181D";
const MUTED = "#8A8D86";
const BODY = "#5B5E64";
const BORDER = "#E4E2DB";
const BG = "#FAFAF8";

// Same schema as app/submit/page.tsx — real field names and limits from
// api/routes/submit.py (biopsy_file 50MB, dna_file 500MB).
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

export default function UploadSection({
  onSubmitted,
}: {
  onSubmitted: (submissionId: string) => void;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const biopsyFile = watch("biopsy_file");
  const dnaFile = watch("dna_file");

  const onSubmit = async (data: FormData) => {
    try {
      const form = new FormData();
      form.append("biopsy_file", data.biopsy_file);
      form.append("dna_file", data.dna_file);
      form.append("cancer_type", data.cancer_type);
      const result = await api.submitSample(form);
      onSubmitted(result.submission_id);
    } catch (err) {
      setError("root", {
        message: err instanceof Error ? err.message : "Upload failed. Please try again.",
      });
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="border p-5"
      style={{ borderColor: BORDER, backgroundColor: "#FFFFFF" }}
    >
      <p className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: MUTED }}>
        POST /api/submit/
      </p>
      <p className="text-sm mb-4" style={{ color: BODY }}>
        Both files are required. Uploaded encrypted, then queued into the genomic pipeline.
      </p>

      <div className="mb-4">
        <label className="text-sm font-semibold" style={{ color: INK }}>
          Cancer type
        </label>
        <input
          {...register("cancer_type")}
          placeholder="e.g. Non-Small Cell Lung Cancer"
          className="mt-1.5 w-full border px-3 py-2 text-sm"
          style={{ borderColor: BORDER, backgroundColor: BG, color: INK }}
        />
        {errors.cancer_type && (
          <p className="text-xs mt-1" style={{ color: "#B3372C" }}>{errors.cancer_type.message}</p>
        )}
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="border p-4" style={{ borderColor: BORDER, backgroundColor: BG }}>
          <p className="text-sm font-semibold" style={{ color: INK }}>Biopsy report</p>
          <p className="font-mono text-[10px] mt-0.5" style={{ color: MUTED }}>
            biopsy_file · PDF, JPG, PNG, TXT, DOC, DOCX, RTF
          </p>
          <label className="mt-3 flex w-full items-center justify-center gap-2 border border-dashed px-4 py-6 text-xs cursor-pointer transition-colors" style={{ borderColor: BORDER, color: biopsyFile ? INK : MUTED }}>
            {biopsyFile ? (
              <>
                <FileCheck2 size={15} /> {biopsyFile.name}
              </>
            ) : (
              <>
                <FileUp size={15} /> Choose file
              </>
            )}
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.txt,.doc,.docx,.rtf,.xml,.json"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && setValue("biopsy_file", e.target.files[0])}
            />
          </label>
          {errors.biopsy_file && (
            <p className="text-xs mt-1" style={{ color: "#B3372C" }}>{errors.biopsy_file.message as string}</p>
          )}
        </div>

        <div className="border p-4" style={{ borderColor: BORDER, backgroundColor: BG }}>
          <p className="text-sm font-semibold" style={{ color: INK }}>DNA / genomic file</p>
          <p className="font-mono text-[10px] mt-0.5" style={{ color: MUTED }}>
            dna_file · VCF, FASTQ, BAM, GZ
          </p>
          <label className="mt-3 flex w-full items-center justify-center gap-2 border border-dashed px-4 py-6 text-xs cursor-pointer transition-colors" style={{ borderColor: BORDER, color: dnaFile ? INK : MUTED }}>
            {dnaFile ? (
              <>
                <FileCheck2 size={15} /> {dnaFile.name}
              </>
            ) : (
              <>
                <FileUp size={15} /> Choose file
              </>
            )}
            <input
              type="file"
              accept=".vcf,.fastq,.fq,.bam,.gz,.txt,.csv,.tsv,.xml,.json"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && setValue("dna_file", e.target.files[0])}
            />
          </label>
          {errors.dna_file && (
            <p className="text-xs mt-1" style={{ color: "#B3372C" }}>{errors.dna_file.message as string}</p>
          )}
        </div>
      </div>

      {errors.root && (
        <div
          className="flex items-center gap-2 mt-4 px-3 py-2 border text-sm"
          style={{ borderColor: "#E8B4AC", backgroundColor: "#FBEEEB", color: "#B3372C" }}
        >
          <AlertCircle size={15} className="shrink-0" /> {errors.root.message}
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        style={{ backgroundColor: INK }}
      >
        {isSubmitting ? "Uploading & encrypting…" : "Submit sample"}
      </button>
    </form>
  );
}

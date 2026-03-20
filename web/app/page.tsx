"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Dna, FlaskConical, HeartHandshake, Shield } from "lucide-react";

const features = [
  {
    icon: Dna,
    title: "Upload Your Genomic Data",
    description:
      "Upload your biopsy PDF or DNA file (VCF/FASTQ). Our pipeline runs FastQC, BWA-MEM2, GATK, and OpenCRAVAT — the same tools used in research hospitals.",
  },
  {
    icon: FlaskConical,
    title: "AI Mutation Analysis",
    description:
      "AlphaFold 3 and AlphaMissense classify every mutation. OncoKB checks clinically actionable targets. DiffDock scores which existing drugs may bind to your mutated protein.",
  },
  {
    icon: HeartHandshake,
    title: "Find Repurposed Drugs",
    description:
      "For targeted mutations, we suggest FDA-approved drugs already used for other cancers that may work for yours. Connected to pharma manufacturers who can produce them.",
  },
  {
    icon: Shield,
    title: "Raise Funds for Treatment",
    description:
      "Can't afford a custom drug? Create a public crowdfunding campaign directly from your results page. Funds are held in escrow and released directly to the manufacturer.",
  },
];

const steps = [
  { step: "01", title: "Create an account", desc: "Free, private, and secure." },
  { step: "02", title: "Upload your sample", desc: "Biopsy PDF + DNA file. Encrypted immediately." },
  { step: "03", title: "Wait ~24 hours", desc: "Pipeline runs automatically. You'll get an email." },
  { step: "04", title: "Review your report", desc: "Plain-language results + drug options." },
  { step: "05", title: "Take action", desc: "Order a drug or start a fundraising campaign." },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
        <span className="font-bold text-xl text-blue-700">OpenOncology</span>
        <div className="flex gap-6 text-sm text-gray-600">
          <Link href="/submit" className="hover:text-blue-700 transition-colors">Submit Sample</Link>
          <Link href="/marketplace" className="hover:text-blue-700 transition-colors">Marketplace</Link>
          <Link href="/dashboard" className="hover:text-blue-700 transition-colors">Dashboard</Link>
        </div>
        <Link
          href="/submit"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          Get Started
        </Link>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <span className="bg-blue-50 text-blue-700 text-xs font-semibold px-3 py-1 rounded-full uppercase tracking-wide">
            Open Source · Free · For Everyone
          </span>
          <h1 className="mt-6 text-5xl font-bold text-gray-900 leading-tight">
            Precision cancer medicine
            <br />
            <span className="text-blue-600">without the price tag.</span>
          </h1>
          <p className="mt-6 text-xl text-gray-600 max-w-2xl mx-auto">
            Upload your DNA or biopsy data. Get AI-powered mutation analysis in 24 hours.
            Find drugs that may already exist for your specific mutation.
            Raise funds if you can't afford treatment.
          </p>
          <div className="mt-10 flex gap-4 justify-center">
            <Link
              href="/submit"
              className="flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition-colors"
            >
              Submit Your Sample <ArrowRight size={18} />
            </Link>
            <a
              href="https://github.com/openoncology"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 border border-gray-200 px-6 py-3 rounded-xl font-semibold text-gray-700 hover:border-gray-400 transition-colors"
            >
              View on GitHub
            </a>
          </div>
        </motion.div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">How it works</h2>
        <div className="grid md:grid-cols-2 gap-8">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              viewport={{ once: true }}
              className="p-6 rounded-2xl border border-gray-100 hover:border-blue-200 hover:shadow-md transition-all"
            >
              <f.icon className="text-blue-600 mb-4" size={32} />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-gray-600 text-sm leading-relaxed">{f.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Steps */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">5 simple steps</h2>
          <div className="space-y-6">
            {steps.map((s) => (
              <div key={s.step} className="flex gap-6 items-start">
                <span className="text-3xl font-bold text-blue-200 w-12 shrink-0">{s.step}</span>
                <div>
                  <h4 className="font-semibold text-gray-900">{s.title}</h4>
                  <p className="text-gray-500 text-sm">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 text-center text-sm text-gray-400">
        OpenOncology · Open source · MIT License ·{" "}
        <a href="https://github.com/openoncology" className="hover:text-blue-600 transition-colors">
          GitHub
        </a>
        <p className="mt-2 text-xs">
          This platform is for research use only. Always consult a qualified oncologist
          before making treatment decisions.
        </p>
      </footer>
    </main>
  );
}

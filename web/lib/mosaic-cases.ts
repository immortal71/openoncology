/**
 * Sample case data for the homepage hero's 3D case cluster.
 * One entry (kras-g12c-nsclc) mirrors the real demo case in demo-data.ts.
 * Gene/drug/score pairs are drawn from real oncology precedent used
 * elsewhere in the app (see components/ui/genomic-stream.tsx).
 */

export type MosaicCase = {
  id: string;
  cancerType: string;
  gene: string;
  hgvs: string;
  oncokbLevel: string;
  candidates: { drug_name: string; rank_score: number }[];
};

export const MOSAIC_CASES: MosaicCase[] = [
  {
    id: "X-2201",
    cancerType: "Non-Small Cell Lung Cancer",
    gene: "KRAS",
    hgvs: "p.Gly12Cys",
    oncokbLevel: "LEVEL_1",
    candidates: [
      { drug_name: "Sotorasib", rank_score: 0.983 },
      { drug_name: "Adagrasib", rank_score: 0.973 },
      { drug_name: "Erlotinib", rank_score: 0.811 },
      { drug_name: "Trametinib", rank_score: 0.642 },
      { drug_name: "Selumetinib", rank_score: 0.518 },
    ],
  },
  {
    id: "X-1847",
    cancerType: "Non-Small Cell Lung Cancer",
    gene: "EGFR",
    hgvs: "p.Leu858Arg",
    oncokbLevel: "LEVEL_1",
    candidates: [
      { drug_name: "Osimertinib", rank_score: 0.923 },
      { drug_name: "Gefitinib", rank_score: 0.834 },
      { drug_name: "Erlotinib", rank_score: 0.795 },
      { drug_name: "Afatinib", rank_score: 0.701 },
    ],
  },
  {
    id: "X-0965",
    cancerType: "Melanoma",
    gene: "BRAF",
    hgvs: "p.Val600Glu",
    oncokbLevel: "LEVEL_1",
    candidates: [
      { drug_name: "Vemurafenib", rank_score: 0.947 },
      { drug_name: "Dabrafenib", rank_score: 0.912 },
      { drug_name: "Trametinib", rank_score: 0.788 },
    ],
  },
  {
    id: "X-3312",
    cancerType: "Breast Cancer",
    gene: "ERBB2",
    hgvs: "p.Val777Leu",
    oncokbLevel: "LEVEL_1",
    candidates: [
      { drug_name: "Trastuzumab", rank_score: 0.891 },
      { drug_name: "Pertuzumab", rank_score: 0.856 },
      { drug_name: "Lapatinib", rank_score: 0.663 },
    ],
  },
  {
    id: "X-4098",
    cancerType: "Colorectal Cancer",
    gene: "PIK3CA",
    hgvs: "p.His1047Arg",
    oncokbLevel: "LEVEL_3B",
    candidates: [
      { drug_name: "Alpelisib", rank_score: 0.744 },
      { drug_name: "Copanlisib", rank_score: 0.601 },
      { drug_name: "Everolimus", rank_score: 0.529 },
    ],
  },
  {
    id: "X-5561",
    cancerType: "Glioblastoma",
    gene: "CDKN2A",
    hgvs: "p.Arg58Ter",
    oncokbLevel: "LEVEL_4",
    candidates: [
      { drug_name: "Palbociclib", rank_score: 0.582 },
      { drug_name: "Ribociclib", rank_score: 0.547 },
      { drug_name: "Abemaciclib", rank_score: 0.503 },
    ],
  },
  {
    id: "X-6273",
    cancerType: "Acute Myeloid Leukemia",
    gene: "FLT3",
    hgvs: "p.Asp835Tyr (ITD)",
    oncokbLevel: "LEVEL_1",
    candidates: [
      { drug_name: "Midostaurin", rank_score: 0.912 },
      { drug_name: "Gilteritinib", rank_score: 0.897 },
      { drug_name: "Sorafenib", rank_score: 0.664 },
    ],
  },
  {
    id: "X-7724",
    cancerType: "Colorectal Cancer",
    gene: "NRAS",
    hgvs: "p.Gln61Lys",
    oncokbLevel: "LEVEL_3A",
    candidates: [
      { drug_name: "Binimetinib", rank_score: 0.678 },
      { drug_name: "Trametinib", rank_score: 0.652 },
      { drug_name: "Selumetinib", rank_score: 0.489 },
    ],
  },
];

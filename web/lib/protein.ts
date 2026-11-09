const AA3: Record<string, string> = {
  Ala: "A",
  Arg: "R",
  Asn: "N",
  Asp: "D",
  Cys: "C",
  Gln: "Q",
  Glu: "E",
  Gly: "G",
  His: "H",
  Ile: "I",
  Leu: "L",
  Lys: "K",
  Met: "M",
  Phe: "F",
  Pro: "P",
  Ser: "S",
  Thr: "T",
  Trp: "W",
  Tyr: "Y",
  Val: "V",
  Ter: "*",
};

export type ProteinChange = { ref: string; position: number; alt: string; short: string };

export function parseProteinChange(hgvs: string | null | undefined): ProteinChange | null {
  const match = hgvs?.trim().match(/^(?:p\.)?([A-Z][a-z]{2}|[A-Z])(\d+)([A-Z][a-z]{2}|[A-Z]|\*|=)$/);
  if (!match) return null;
  const toOne = (s: string) => (s.length === 3 ? AA3[s] : s);
  const ref = toOne(match[1]);
  const alt = match[3] === "=" ? ref : toOne(match[3]);
  if (!ref || !alt) return null;
  const position = Number(match[2]);
  return { ref, position, alt, short: `${ref}${position}${alt}` };
}

export type ProteinReference = {
  length: number;
  source: string;
  domains: { label: string; short: string; start: number; end: number }[];
};

export const PROTEIN_REFERENCE: Record<string, ProteinReference> = {
  KRAS: { length: 189, source: "UniProt P01116-1", domains: [{ label: "P-loop", short: "P-loop", start: 10, end: 17 }] },
  TP53: { length: 393, source: "UniProt P04637", domains: [{ label: "DNA-binding domain", short: "DBD", start: 94, end: 292 }] },
};

export function domainAt(gene: string, position: number): string | null {
  const ref = PROTEIN_REFERENCE[gene.toUpperCase()];
  return ref?.domains.find((d) => position >= d.start && position <= d.end)?.label ?? null;
}

"""Analytical validation gate: variant calling accuracy vs. a truth set.

WHAT THIS MEASURES
------------------
docs/REGULATORY_FRAMEWORK.md section 3.1 lists "Variant calling accuracy
(SNV/indel) vs. orthogonal WGS, sensitivity >= 99%, PPV >= 95%" as the one
analytical gate with no measurement at all. docs/risk_analysis.md carries the
same gap as F6 and rates it the dominant uncontrolled hazard, because every
recommendation the system makes is conditioned on the variant call being
correct.

This script is the measuring instrument for that gate. It compares a query VCF
against the Genome in a Bottle HG002 benchmark call set, restricted to the
high-confidence regions NIST publishes with it, and reports sensitivity, PPV
and F1, stratified into SNVs and indels.

TWO THINGS IT CAN BE POINTED AT
-------------------------------
1. --query <calls.vcf> [more.vcf ...]
   Calls to evaluate. Several files are scored as one call set, which is how a
   caller that writes SNPs and indels separately is handled.

   Pointed at output from pipeline/main.nf on HG002 reads, this answers the
   gate. That needs bwa-mem2, gatk, samtools and a GRCh38 reference, and does
   not run on a developer workstation.

   Pointed at a published HG002 call set from a comparable pipeline, it
   measures that pipeline rather than this one. Useful as a reference figure
   and as an end-to-end exercise of this harness on genuinely discordant data,
   but it is not this repository's caller and must not be recorded as though it
   were.

2. --via-parser
   The benchmark call set fed through the production ingestion path,
   api.workers.genomic_worker._parse_and_annotate_vcf, and compared back
   against itself. The caller is held constant at "perfect", so every variant
   lost is lost by ingestion. This measures the stage of the pipeline that is
   pure Python, and it runs anywhere.

Mode 2 does NOT satisfy the gate. It bounds one stage. A pipeline cannot be
more accurate end to end than its ingestion step, so mode 2 produces a ceiling
on mode 1 and nothing else. Quoting a mode 2 number as "variant calling
accuracy" would be the same category of error as the circular concordance
benchmark in docs/ONCOLOGIST_CONCORDANCE_PLAIN_LANGUAGE.md.

READ THIS BEFORE QUOTING ANY NUMBER
-----------------------------------
* Comparison is by normalised allele identity, not by haplotype. Two callers
  can write the same indel at different positions with different padding, and
  this script resolves that only as far as trimming common prefixes and
  suffixes. Full resolution needs left-alignment against the reference genome,
  which needs the reference. hap.py and rtg vcfeval do haplotype-aware
  comparison and are the right tools once the toolchain exists. Against a real
  caller this script therefore UNDERSTATES indel recall. It does not understate
  SNV recall, and in mode 2 it understates nothing, because both sides of the
  comparison come from the same file and the same writer.
* Only variants inside the NIST high-confidence BED are counted, on both sides.
  A call outside those regions is neither a true positive nor a false positive.
  It is not evaluated at all. That is how GIAB is meant to be used, and it
  means the result says nothing about difficult regions.
* Default scope is chr20, the chromosome conventionally held out for evaluation
  in GIAB-based benchmarking. --chrom all runs the genome and needs
  substantially more memory and time.
* Genotype is not compared unless --match-genotype is passed. Without it, a
  heterozygous call where the truth is homozygous counts as a true positive.

Usage:
    python scripts/validate_variant_calling.py --via-parser
    python scripts/validate_variant_calling.py --query pipeline/results/hg002.vcf
    python scripts/validate_variant_calling.py --query snp.vcf.gz indel.vcf.gz
    python scripts/validate_variant_calling.py --query calls.vcf --chrom all --gate
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import itertools
import json
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# GIAB HG002 v4.2.1 on GRCh38. Public NIST release, no credentials needed.
_GIAB_BASE = (
    "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/"
    "AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/GRCh38/"
)
_TRUTH_VCF = "HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz"
_TRUTH_BED = "HG002_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed"
_CACHE = _REPO_ROOT / "validation_results" / "cache"
_RESULT = _REPO_ROOT / "validation_results" / "variant_calling_accuracy.json"

# The gate thresholds in docs/REGULATORY_FRAMEWORK.md section 3.1.
_TARGET_SENSITIVITY = 0.99
_TARGET_PPV = 0.95


# -- VCF reading --------------------------------------------------------------

def _open_maybe_gzip(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path, "r")


def norm_chrom(chrom: str) -> str:
    """chr20 and 20 are the same contig. Compare without the prefix."""
    c = chrom.strip()
    return c[3:] if c.lower().startswith("chr") else c


def normalise_allele(pos: int, ref: str, alt: str) -> tuple[int, str, str]:
    """Reduce a variant to its minimal representation.

    Trims the common suffix, then the common prefix, never emptying either
    allele, and moves POS forward by whatever came off the front. This is the
    standard trim step. It is not left-alignment: an indel in a homopolymer can
    still be written at several positions and only the reference genome can
    collapse those to one.
    """
    ref = ref.upper()
    alt = alt.upper()
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    trimmed = 0
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref, alt = ref[1:], alt[1:]
        trimmed += 1
    return pos + trimmed, ref, alt


def is_snv(ref: str, alt: str) -> bool:
    return len(ref) == 1 and len(alt) == 1 and ref != alt


def _extract_gt(parts: list[str]) -> str:
    if len(parts) < 10:
        return ""
    fmt = parts[8].split(":")
    if "GT" not in fmt:
        return ""
    sample = parts[9].split(":")
    idx = fmt.index("GT")
    if idx >= len(sample):
        return ""
    return sample[idx].replace("|", "/")


def iter_vcf_variants(
    path: Path,
    chroms: Optional[set[str]] = None,
    pass_only: bool = True,
) -> Iterator[tuple[str, int, str, str, str]]:
    """Yield (chrom, pos, ref, alt, gt) per ALT allele, normalised.

    Multi-allelic records are split, which is the property the production
    parser had to be fixed to hold (docs/risk_analysis.md F8).
    """
    with _open_maybe_gzip(path) as fh:
        for line in fh:
            if not line or line[0] == "#":
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 8:
                continue
            chrom = norm_chrom(parts[0])
            if chroms is not None and chrom not in chroms:
                continue
            if not parts[1].isdigit():
                continue
            pos = int(parts[1])
            ref, alt_field = parts[3], parts[4]
            filt = (parts[6] or "").strip()
            if pass_only and filt.upper() not in ("PASS", ".", ""):
                continue
            gt = _extract_gt(parts)
            for allele in alt_field.split(","):
                allele = allele.strip()
                if not allele or allele in ("*", "."):
                    continue
                npos, nref, nalt = normalise_allele(pos, ref, allele)
                yield (chrom, npos, nref, nalt, gt)


# -- Confident regions --------------------------------------------------------

class ConfidentRegions:
    """BED intervals with binary-search membership. BED is 0-based half-open."""

    def __init__(self, starts: dict[str, list[int]], ends: dict[str, list[int]]):
        self._starts = starts
        self._ends = ends

    @classmethod
    def from_bed(
        cls, path: Path, chroms: Optional[set[str]] = None
    ) -> "ConfidentRegions":
        raw: dict[str, list[tuple[int, int]]] = {}
        with _open_maybe_gzip(path) as fh:
            for line in fh:
                if not line.strip() or line.startswith(("#", "track", "browser")):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                chrom = norm_chrom(parts[0])
                if chroms is not None and chrom not in chroms:
                    continue
                try:
                    s, e = int(parts[1]), int(parts[2])
                except ValueError:
                    continue
                if e <= s:
                    continue
                raw.setdefault(chrom, []).append((s, e))
        starts: dict[str, list[int]] = {}
        ends: dict[str, list[int]] = {}
        for chrom, ivals in raw.items():
            ivals.sort()
            # Merge overlaps so a single binary search answers membership.
            merged: list[tuple[int, int]] = []
            for s, e in ivals:
                if merged and s <= merged[-1][1]:
                    if e > merged[-1][1]:
                        merged[-1] = (merged[-1][0], e)
                else:
                    merged.append((s, e))
            starts[chrom] = [s for s, _ in merged]
            ends[chrom] = [e for _, e in merged]
        return cls(starts, ends)

    def contains(self, chrom: str, pos: int) -> bool:
        """pos is a 1-based VCF POS."""
        s = self._starts.get(chrom)
        if not s:
            return False
        p0 = pos - 1
        i = bisect.bisect_right(s, p0) - 1
        if i < 0:
            return False
        return p0 < self._ends[chrom][i]

    def interval_count(self) -> int:
        return sum(len(v) for v in self._starts.values())

    def base_count(self) -> int:
        return sum(
            e - s
            for chrom in self._starts
            for s, e in zip(self._starts[chrom], self._ends[chrom])
        )


# -- Comparison ---------------------------------------------------------------

def _blank_counts() -> dict[str, int]:
    return {"tp": 0, "fp": 0, "fn": 0}


def _metrics(counts: dict[str, int]) -> dict[str, object]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    sensitivity = tp / (tp + fn) if (tp + fn) else None
    ppv = tp / (tp + fp) if (tp + fp) else None
    f1 = None
    if sensitivity is not None and ppv is not None and (sensitivity + ppv) > 0:
        f1 = 2 * sensitivity * ppv / (sensitivity + ppv)
    return {
        "truth_total": tp + fn,
        "query_total": tp + fp,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "sensitivity": sensitivity,
        "ppv": ppv,
        "f1": f1,
        "meets_sensitivity_target": (
            None if sensitivity is None else sensitivity >= _TARGET_SENSITIVITY
        ),
        "meets_ppv_target": None if ppv is None else ppv >= _TARGET_PPV,
    }


def compare(
    truth: Iterator[tuple[str, int, str, str, str]],
    query: Iterator[tuple[str, int, str, str, str]],
    regions: Optional[ConfidentRegions] = None,
    match_genotype: bool = False,
) -> dict[str, object]:
    """Compare two variant streams and return stratified metrics.

    Truth is materialised into a dict keyed by normalised allele identity; the
    query is streamed against it. Memory is therefore bounded by the truth set
    inside the confident regions, which is why --chrom defaults to one
    chromosome.
    """
    truth_map: dict[tuple[str, int, str, str], str] = {}
    for chrom, pos, ref, alt, gt in truth:
        if regions is not None and not regions.contains(chrom, pos):
            continue
        truth_map[(chrom, pos, ref, alt)] = gt

    matched: set[tuple[str, int, str, str]] = set()
    counts = {"snv": _blank_counts(), "indel": _blank_counts(), "all": _blank_counts()}
    genotype_mismatches = 0
    query_outside_regions = 0

    for chrom, pos, ref, alt, gt in query:
        if regions is not None and not regions.contains(chrom, pos):
            query_outside_regions += 1
            continue
        stratum = "snv" if is_snv(ref, alt) else "indel"
        key = (chrom, pos, ref, alt)
        if key in truth_map:
            if match_genotype and truth_map[key] and gt and truth_map[key] != gt:
                genotype_mismatches += 1
                counts[stratum]["fp"] += 1
                counts["all"]["fp"] += 1
                continue
            if key in matched:
                # A duplicate query record for an already-matched truth variant
                # is not a second true positive.
                counts[stratum]["fp"] += 1
                counts["all"]["fp"] += 1
                continue
            matched.add(key)
            counts[stratum]["tp"] += 1
            counts["all"]["tp"] += 1
        else:
            counts[stratum]["fp"] += 1
            counts["all"]["fp"] += 1

    for key in truth_map:
        if key in matched:
            continue
        stratum = "snv" if is_snv(key[2], key[3]) else "indel"
        counts[stratum]["fn"] += 1
        counts["all"]["fn"] += 1

    return {
        "overall": _metrics(counts["all"]),
        "snv": _metrics(counts["snv"]),
        "indel": _metrics(counts["indel"]),
        "genotype_mismatches": genotype_mismatches,
        "query_records_outside_confident_regions": query_outside_regions,
    }


# -- Data acquisition ---------------------------------------------------------

def ensure_truth_set(offline: bool = False) -> tuple[Path, Path]:
    _CACHE.mkdir(parents=True, exist_ok=True)
    vcf, bed = _CACHE / _TRUTH_VCF, _CACHE / _TRUTH_BED
    for dest, name in ((bed, _TRUTH_BED), (vcf, _TRUTH_VCF)):
        if dest.exists() and dest.stat().st_size > 0:
            continue
        if offline:
            raise SystemExit(
                f"missing {dest} and --offline was passed. Fetch it from {_GIAB_BASE}{name}"
            )
        print(f"[giab] downloading {name} ...", flush=True)
        started = time.time()
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(_GIAB_BASE + name, tmp)
        tmp.replace(dest)
        print(
            f"[giab] {name} {dest.stat().st_size:,} bytes in {time.time() - started:.0f}s",
            flush=True,
        )
    return vcf, bed


def _materialise_plaintext_subset(
    src: Path, chroms: Optional[set[str]], dest: Path
) -> dict[str, int]:
    """Write a plain-text VCF of the selected contigs and characterise it.

    The production parser opens its input with a bare open(), so a gzipped
    truth set has to be expanded before it can be fed through the real
    ingestion path rather than a reimplementation of it.

    The counts returned are what makes the resulting score readable. A 100%
    ingestion score over an input containing no rejected calls does not show
    that rejected calls are handled, it shows that none were present. See
    path_coverage in the output.
    """
    stats = {
        "records": 0,
        "alt_alleles": 0,
        "multi_allelic_records": 0,
        "caller_rejected_records": 0,
        "malformed_records": 0,
    }
    with _open_maybe_gzip(src) as fh, open(dest, "w") as out:
        for line in fh:
            if line.startswith("#"):
                out.write(line)
                continue
            tab = line.find("\t")
            if tab < 0:
                continue
            if chroms is not None and norm_chrom(line[:tab]) not in chroms:
                continue
            out.write(line)
            stats["records"] += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 8 or not parts[1].isdigit():
                stats["malformed_records"] += 1
                continue
            if (parts[6] or "").strip().upper() not in ("PASS", ".", ""):
                stats["caller_rejected_records"] += 1
            alts = [a for a in parts[4].split(",") if a not in ("*", ".", "")]
            stats["alt_alleles"] += len(alts)
            if len(alts) > 1:
                stats["multi_allelic_records"] += 1
    return stats


# Which finding each ingestion behaviour came from, so a run can say which of
# them its input actually put under load. docs/risk_analysis.md section 2.
_PATH_FINDINGS = {
    "multi_allelic_records": "F8 multi-allelic splitting",
    "caller_rejected_records": "F7 caller-rejected calls dropped",
    "malformed_records": "malformed-record guards",
}


def summarise_path_coverage(stats: dict[str, int]) -> dict[str, object]:
    exercised, unexercised = [], []
    for key, label in _PATH_FINDINGS.items():
        (exercised if stats.get(key) else unexercised).append(
            f"{label} (n={stats.get(key, 0)})"
        )
    return {
        "input": dict(stats),
        "exercised": exercised,
        "not_exercised": unexercised,
        "note": (
            "A path with no instances in the input was not tested by this run. "
            "The score says nothing about it either way."
        ),
    }


def _parser_query_stream(
    truth_vcf: Path, chroms: Optional[set[str]], stats_out: dict
) -> Iterator[tuple[str, int, str, str, str]]:
    """Run the truth set through the production ingestion path."""
    import logging

    from api.workers.genomic_worker import _parse_and_annotate_vcf

    # The parser logs one INFO line per rejected call, which is the right
    # behaviour in production and unreadable across a whole chromosome. The
    # count of what it dropped is recovered from the comparison, not the log.
    logging.getLogger("api.workers.genomic_worker").setLevel(logging.WARNING)
    logging.getLogger("workers.genomic_worker").setLevel(logging.WARNING)

    with tempfile.TemporaryDirectory() as td:
        plain = Path(td) / "truth_subset.vcf"
        stats = _materialise_plaintext_subset(truth_vcf, chroms, plain)
        stats_out.update(stats)
        print(
            f"[parser] {stats['records']:,} records in, "
            f"{stats['alt_alleles']:,} alt alleles, "
            f"{stats['multi_allelic_records']:,} multi-allelic, "
            f"{stats['caller_rejected_records']:,} caller-rejected",
            flush=True,
        )
        mutations = _parse_and_annotate_vcf(str(plain))
        print(f"[parser] {len(mutations):,} mutations returned", flush=True)
        for m in mutations:
            if m.get("pos") is None:
                continue
            npos, nref, nalt = normalise_allele(
                int(m["pos"]), str(m["ref"]), str(m["alt"])
            )
            yield (norm_chrom(str(m["chrom"])), npos, nref, nalt, "")


# -- CLI ----------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--query",
        nargs="+",
        help="VCF(s) of calls to evaluate. Several are treated as one call set, "
        "which is how callers that emit SNPs and indels separately are scored. "
        "Omit with --via-parser to use the truth set.",
    )
    ap.add_argument(
        "--via-parser",
        action="store_true",
        help="Feed the query through the production ingestion path first. "
        "With no --query this measures ingestion fidelity on the truth set.",
    )
    ap.add_argument("--truth", help="Truth VCF (defaults to the cached GIAB release)")
    ap.add_argument("--bed", help="High-confidence BED (defaults to the cached GIAB release)")
    ap.add_argument(
        "--chrom",
        default="chr20",
        help="Contig to evaluate, or 'all'. Default chr20, the conventional "
        "held-out evaluation chromosome.",
    )
    ap.add_argument(
        "--from-repo-pipeline",
        action="store_true",
        help="Assert that --query was produced by this repository's "
        "pipeline/main.nf. Without it a run is recorded as measuring some other "
        "call set, and cannot satisfy the REGULATORY_FRAMEWORK.md 3.1 gate no "
        "matter how good the numbers are.",
    )
    ap.add_argument(
        "--query-label",
        help="Free text describing the call set, stored in the result file "
        "(e.g. 'NIST BGIseq 100x, GATK HaplotypeCaller 4.1.4.1').",
    )
    ap.add_argument("--match-genotype", action="store_true")
    ap.add_argument(
        "--query-include-filtered",
        action="store_true",
        help="Count calls the caller rejected as query calls. Off by default, "
        "because the production parser drops them (docs/risk_analysis.md F7), "
        "so counting them would score the caller on variants the pipeline "
        "never ingests.",
    )
    ap.add_argument("--no-regions", action="store_true", help="Skip BED restriction")
    ap.add_argument("--offline", action="store_true", help="Never download")
    ap.add_argument(
        "--gate",
        action="store_true",
        help="Exit non-zero unless the overall stratum meets both targets.",
    )
    ap.add_argument("--out", default=str(_RESULT))
    args = ap.parse_args(argv)

    if not args.query and not args.via_parser:
        ap.error("pass --query, or --via-parser to measure the ingestion stage")

    if args.truth and args.bed:
        truth_vcf, bed_path = Path(args.truth), Path(args.bed)
    else:
        truth_vcf, bed_path = ensure_truth_set(offline=args.offline)
        if args.truth:
            truth_vcf = Path(args.truth)
        if args.bed:
            bed_path = Path(args.bed)

    chroms: Optional[set[str]] = None
    if args.chrom.lower() != "all":
        chroms = {norm_chrom(c) for c in args.chrom.split(",")}

    regions = None
    if not args.no_regions:
        print(f"[bed] loading {bed_path.name} ...", flush=True)
        regions = ConfidentRegions.from_bed(bed_path, chroms)
        print(
            f"[bed] {regions.interval_count():,} intervals, "
            f"{regions.base_count():,} bases",
            flush=True,
        )

    mode = "ingestion_fidelity" if (args.via_parser and not args.query) else "variant_calling"
    query_paths = [Path(q) for q in (args.query or [])] or [truth_vcf]
    for qp in query_paths:
        if not qp.exists():
            ap.error(f"query VCF not found: {qp}")

    print(f"[run] mode={mode} chrom={args.chrom}", flush=True)
    if args.query:
        for qp in query_paths:
            print(f"[query] {qp.name}", flush=True)
    truth_stream = iter_vcf_variants(truth_vcf, chroms)
    ingestion_stats: dict[str, int] = {}
    if args.via_parser:
        query_stream = _parser_query_stream(query_paths[0], chroms, ingestion_stats)
    else:
        query_stream = itertools.chain.from_iterable(
            iter_vcf_variants(qp, chroms, pass_only=not args.query_include_filtered)
            for qp in query_paths
        )

    started = time.time()
    result = compare(truth_stream, query_stream, regions, args.match_genotype)
    elapsed = time.time() - started

    payload = {
        "gate": "variant_calling_accuracy",
        "mode": mode,
        "measures": (
            "Fidelity of the production VCF ingestion path only. This is a "
            "ceiling on end-to-end variant calling accuracy, not a measurement "
            "of it. The gate in REGULATORY_FRAMEWORK.md 3.1 remains unmet."
            if mode == "ingestion_fidelity"
            else "End-to-end variant calling accuracy against GIAB HG002."
        ),
        "truth_set": {
            "name": "GIAB HG002 NISTv4.2.1 GRCh38",
            "vcf": truth_vcf.name,
            "bed": None if regions is None else bed_path.name,
            "source": _GIAB_BASE,
        },
        "query": None if not args.query else [str(q) for q in query_paths],
        "query_label": args.query_label,
        "query_from_repo_pipeline": bool(args.from_repo_pipeline),
        "scope": {
            "chrom": args.chrom,
            "confident_regions_only": regions is not None,
            "genotype_compared": args.match_genotype,
            "caller_rejected_query_calls_counted": args.query_include_filtered,
        },
        "targets": {"sensitivity": _TARGET_SENSITIVITY, "ppv": _TARGET_PPV},
        "results": result,
        "elapsed_seconds": round(elapsed, 1),
        "caveats": [
            "Allele-identity comparison after trimming, not haplotype comparison. "
            "Indel recall is understated against a real caller; use hap.py or rtg "
            "vcfeval once the toolchain exists.",
            "Only variants inside the NIST high-confidence BED are evaluated.",
            "Genotype is not compared unless --match-genotype was passed.",
        ],
    }
    if mode == "ingestion_fidelity":
        coverage = summarise_path_coverage(ingestion_stats)
        payload["path_coverage"] = coverage
        payload["caveats"].insert(
            0,
            "Both sides of this comparison come from the same file. It cannot "
            "detect an error made by the variant caller, because no variant "
            "caller ran.",
        )
        if coverage["not_exercised"]:
            payload["caveats"].insert(
                1,
                "This input did not contain instances of: "
                + "; ".join(coverage["not_exercised"])
                + ". A perfect score is silent about those paths rather than "
                "evidence in their favour.",
            )

    ov_pre = result["overall"]
    meets = bool(ov_pre["meets_sensitivity_target"] and ov_pre["meets_ppv_target"])
    if mode != "variant_calling":
        gate_status = (
            "not applicable: this run measured the ingestion path, no caller ran"
        )
    elif not args.from_repo_pipeline:
        gate_status = (
            "not satisfied: the call set was not asserted to come from this "
            "repository's pipeline/main.nf, so it measures some other pipeline "
            "however good the numbers are"
        )
    elif not meets:
        gate_status = "not satisfied: this pipeline's calls missed a target"
    else:
        gate_status = "satisfied"
    payload["satisfies_regulatory_gate_3_1"] = (
        mode == "variant_calling" and bool(args.from_repo_pipeline) and meets
    )
    payload["gate_status"] = gate_status

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    ov = result["overall"]
    print()
    print(f"  truth variants evaluated : {ov['truth_total']:,}")
    print(f"  query variants evaluated : {ov['query_total']:,}")
    print(f"  TP / FP / FN             : {ov['tp']:,} / {ov['fp']:,} / {ov['fn']:,}")
    for stratum in ("overall", "snv", "indel"):
        m = result[stratum]
        sens = "n/a" if m["sensitivity"] is None else f"{m['sensitivity'] * 100:.4f}%"
        ppv = "n/a" if m["ppv"] is None else f"{m['ppv'] * 100:.4f}%"
        print(f"  {stratum:<8} sensitivity {sens:>12}   PPV {ppv:>12}   n={m['truth_total']:,}")
    print()
    print(f"  REGULATORY_FRAMEWORK.md 3.1 gate: {gate_status}")
    print(f"  written to {out_path}")
    if mode == "ingestion_fidelity":
        cov = payload["path_coverage"]
        print()
        print("  Ingestion paths this input put under load:")
        for item in cov["exercised"]:
            print(f"    exercised     {item}")
        for item in cov["not_exercised"]:
            print(f"    NOT exercised {item}")
        print()
        print("  This is ingestion fidelity, not variant calling accuracy.")
        print("  REGULATORY_FRAMEWORK.md 3.1 variant calling remains NOT MEASURED.")
        if cov["not_exercised"]:
            print("  The score above is silent about every path marked NOT exercised.")

    if args.gate:
        ok = ov["meets_sensitivity_target"] and ov["meets_ppv_target"]
        if not ok:
            print("\n  GATE FAILED", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

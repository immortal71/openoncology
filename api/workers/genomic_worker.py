"""
Genomic Worker — runs the Nextflow bioinformatics pipeline on patient DNA files.

Pipeline steps:
  1. Download DNA file from MinIO
  2. Run Nextflow: FastQC → Trimmomatic → BWA-MEM2 → GATK → OpenCRAVAT
  3. Parse VCF output — extract mutations
  4. Store mutations in DB, update submission status
  5. Queue AI worker for classification + repurposing
"""
import shutil
import subprocess
import tempfile
import os
import logging

from workers import celery_app
from config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.genomic_worker.run_genomic_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_genomic_pipeline(
    self,
    submission_id: str,
    patient_id: str,
    biopsy_s3_key: str,
    dna_s3_key: str,
    cancer_type: str,
):
    """
    Main genomic pipeline task.
    Runs synchronously inside the Celery worker process.
    """
    from workers._db_sync import get_sync_session
    from models.submission import Submission, SubmissionStatus
    from models.mutation import Mutation, MutationClassification, OncoKBLevel

    logger.info(f"[genomic] Starting pipeline for submission {submission_id}")

    with get_sync_session() as db:
        submission = db.get(Submission, submission_id)
        if not submission:
            logger.error(f"[genomic] Submission {submission_id} not found")
            return
        submission.status = SubmissionStatus.processing
        db.commit()

    try:
        with tempfile.TemporaryDirectory() as workdir:
            # 1. Download DNA file from MinIO
            dna_local = _download_from_minio(dna_s3_key, workdir)

            # 2. Run Nextflow pipeline
            vcf_path = _run_nextflow_pipeline(dna_local, workdir, cancer_type)

            # 3. Parse VCF and annotate mutations
            mutations_data = _parse_and_annotate_vcf(vcf_path)

            # 3b. Sample QC. services/sample_qc.py implements FFPE artefact
            # detection, tumour purity and coverage, and nothing in the pipeline
            # had ever called it, so the control was inert: a sample with a
            # high-confidence FFPE signal produced recommendations exactly like
            # a clean one. The verdict is persisted on the submission so it
            # reaches the oncologist report rather than living only in logs.
            qc_report = _run_sample_qc_checkpoint(vcf_path, submission_id)

            # 4. Upload annotated VCF back to MinIO
            vcf_s3_key = _upload_vcf_to_minio(vcf_path, patient_id, submission_id)

            # 5. Store mutations in DB
            with get_sync_session() as db:
                for m in mutations_data:
                    mutation = Mutation(
                        submission_id=submission_id,
                        gene=m.get("gene", "UNKNOWN"),
                        hgvs_notation=m.get("hgvs"),
                        mutation_type=m.get("mutation_type"),
                        chromosome=m.get("chrom"),
                        position=m.get("pos"),
                        ref_allele=m.get("ref"),
                        alt_allele=m.get("alt"),
                        classification=MutationClassification.uncertain,
                        oncokb_level=OncoKBLevel.unknown,
                        clinvar_id=m.get("clinvar_id"),
                        cosmic_id=m.get("cosmic_id"),
                    )
                    db.add(mutation)

                submission = db.get(Submission, submission_id)
                submission.status = SubmissionStatus.awaiting_ai
                submission.vcf_s3_key = vcf_s3_key
                if qc_report is not None:
                    from services.sample_qc import sample_qc_to_report_dict

                    submission.sample_qc = sample_qc_to_report_dict(qc_report)
                db.commit()

        # 6. Queue AI worker
        from workers.ai_worker import run_ai_analysis
        job = run_ai_analysis.apply_async(
            args=[submission_id, patient_id, vcf_s3_key, cancer_type],
            queue="ai",
        )

        with get_sync_session() as db:
            submission = db.get(Submission, submission_id)
            submission.ai_job_id = job.id
            db.commit()

        logger.info(f"[genomic] Pipeline complete for {submission_id}. AI job: {job.id}")

    except Exception as exc:
        logger.error(f"[genomic] Pipeline failed for {submission_id}: {exc}")
        with get_sync_session() as db:
            submission = db.get(Submission, submission_id)
            if submission:
                submission.status = SubmissionStatus.failed
                db.commit()
        raise self.retry(exc=exc)


def _download_from_minio(s3_key: str, workdir: str) -> str:
    """Download a file from MinIO to local temp dir. Returns local path."""
    import boto3
    from botocore.config import Config
    from config import settings

    scheme = "https" if settings.minio_secure else "http"
    s3 = boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    local_path = os.path.join(workdir, os.path.basename(s3_key))
    s3.download_file(settings.bucket_raw, s3_key, local_path)
    return local_path


def _run_nextflow_pipeline(dna_file: str, workdir: str, cancer_type: str) -> str:
    """
    Execute the Nextflow pipeline. Returns path to output VCF.
    Nextflow handles: FastQC → Trimmomatic → BWA-MEM2 → GATK → OpenCRAVAT

    Dev-mode shortcut: pre-called VCF input already carries GENE/HGVS/CLINVAR/
    COSMIC annotations (see samples/), and Nextflow itself isn't installed in
    the local dev image (it needs Conda + OpenCRAVAT's multi-GB reference DBs).
    main.nf takes the same shortcut for .vcf input — skip straight to OpenCRAVAT
    — so locally we skip straight to treating the input as already-annotated.
    """
    if (
        settings.environment == "development"
        and shutil.which("nextflow") is None
        and dna_file.lower().endswith((".vcf", ".vcf.gz"))
    ):
        output_dir = os.path.join(workdir, "results")
        os.makedirs(output_dir, exist_ok=True)
        annotated_path = os.path.join(
            output_dir, os.path.basename(dna_file).rsplit(".", 1)[0] + ".annotated.vcf"
        )
        shutil.copyfile(dna_file, annotated_path)
        logger.warning(
            "[genomic] DEV MODE: nextflow not installed — using input VCF as "
            "pre-annotated output instead of running the real OpenCRAVAT pipeline."
        )
        return annotated_path

    pipeline_dir = os.path.join(os.path.dirname(__file__), "..", "..", "pipeline")
    output_dir = os.path.join(workdir, "results")
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "nextflow", "run", os.path.join(pipeline_dir, "main.nf"),
        "--input_file", dna_file,
        "--output_dir", output_dir,
        "--cancer_type", cancer_type,
        "-work-dir", os.path.join(workdir, "work"),
        "-with-report",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=workdir,
        timeout=7200,  # 2 hour timeout
    )

    if result.returncode != 0:
        raise RuntimeError(f"Nextflow pipeline failed:\n{result.stderr}")

    # Find output VCF in results dir
    for fname in os.listdir(output_dir):
        if fname.endswith(".annotated.vcf"):
            return os.path.join(output_dir, fname)

    raise FileNotFoundError("Annotated VCF not found after pipeline run")


def _run_sample_qc_checkpoint(vcf_path: str, submission_id: str) -> "object | None":
    """Run sample QC and record the verdict. Never fails the submission.

    QC is advisory here. A FAIL verdict means the sample looks unreliable, most
    often a high-confidence FFPE deamination signal, and that has to be visible
    to whoever reads the result. Raising instead would discard a real analysis
    over a quality signal, so this logs at the severity the verdict warrants and
    returns the report for callers that want it.
    """
    try:
        from services.sample_qc import run_sample_qc

        report = run_sample_qc(vcf_path)
    except Exception as exc:  # QC must never take down the analysis
        logger.warning("[genomic] sample QC did not run for %s: %s", submission_id, exc)
        return None

    detail = (
        f"verdict={report.verdict} ffpe_score={report.ffpe.ffpe_score} "
        f"ffpe_flagged={report.ffpe.is_flagged} variants={report.total_variants}"
    )
    if report.verdict == "FAIL":
        logger.error(
            "[genomic] sample QC FAILED for submission %s (%s); reasons: %s",
            submission_id, detail, "; ".join(report.verdict_reasons) or "none recorded",
        )
    elif report.verdict == "WARN":
        logger.warning(
            "[genomic] sample QC warning for submission %s (%s); reasons: %s",
            submission_id, detail, "; ".join(report.verdict_reasons) or "none recorded",
        )
    else:
        logger.info("[genomic] sample QC passed for submission %s (%s)", submission_id, detail)

    return report


# FILTER values that mean "the caller did not reject this call". Anything else
# is an explicit rejection and must not reach a treatment recommendation.
# "." and "" mean no filtering was applied rather than a failure, so they pass.
_ACCEPTED_FILTERS = {"PASS", ".", ""}


def _extract_vaf_and_depth(parts: list[str]) -> tuple[float | None, int | None]:
    """Pull VAF and depth out of the FORMAT/sample columns, if present.

    Without this the mutation dicts carry no allele fraction, which means the
    FFPE artefact detector in services/sample_qc.py cannot be applied to
    anything ingested here: a 2% deamination artefact and a clonal driver look
    identical downstream.
    """
    if len(parts) < 10:
        return None, None
    keys = parts[8].split(":")
    values = parts[9].split(":")
    if len(keys) != len(values):
        return None, None
    field = dict(zip(keys, values))

    depth = None
    raw_depth = field.get("DP")
    if raw_depth and raw_depth.isdigit():
        depth = int(raw_depth)

    # AF directly, when the caller emits it.
    raw_af = field.get("AF")
    if raw_af and raw_af not in (".", ""):
        try:
            return float(raw_af.split(",")[0]), depth
        except ValueError:
            pass

    # Otherwise derive it from allelic depths.
    raw_ad = field.get("AD")
    if raw_ad and raw_ad not in (".", ""):
        try:
            counts = [int(x) for x in raw_ad.split(",") if x not in (".", "")]
        except ValueError:
            return None, depth
        total = sum(counts)
        if total > 0 and len(counts) >= 2:
            return sum(counts[1:]) / total, depth or total

    return None, depth


def _parse_and_annotate_vcf(vcf_path: str, include_filtered: bool = False) -> list[dict]:
    """
    Parse the OpenCRAVAT-annotated VCF file.
    Returns a list of mutation dicts with gene, hgvs, clinvar, cosmic etc.

    Three properties this must hold, each of which it previously did not:

    * A multi-allelic site is several variants, not one. ALT "GGTTT,GTTTT" used
      to be stored verbatim as a single alt string, which matches no evidence
      record, so if one of the alleles was the actionable one it was lost.
      Nothing upstream normalises: there is no bcftools norm step in
      pipeline/. Each ALT allele is now emitted as its own mutation.
    * A call the variant caller rejected must not silently become a
      recommendation. FILTER was unpacked and discarded, so Mutect2's
      weak_evidence, strand_bias and panel_of_normals calls were ingested
      exactly like PASS calls. They are now dropped by default and the value is
      retained either way so the decision is visible.
    * VAF and depth are carried through, so low-allele-fraction artefacts are
      distinguishable downstream.
    """
    mutations = []
    with open(vcf_path, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, _vid, ref, alt, _qual, filt, info = parts[:8]

            filter_status = (filt or "").strip()
            passed = filter_status.upper() in {v.upper() for v in _ACCEPTED_FILTERS}
            if not passed and not include_filtered:
                logger.info(
                    "[vcf] dropping %s:%s %s>%s rejected by the caller (FILTER=%s)",
                    chrom, pos, ref, alt, filter_status,
                )
                continue

            # Parse INFO field for OpenCRAVAT annotations
            info_dict = dict(
                kv.split("=", 1) if "=" in kv else (kv, "true")
                for kv in info.split(";")
            )

            vaf, depth = _extract_vaf_and_depth(parts)

            # A multi-allelic record describes several distinct variants.
            for allele in (a.strip() for a in alt.split(",")):
                if not allele:
                    continue
                mutations.append({
                    "chrom": chrom,
                    "pos": int(pos) if pos.isdigit() else None,
                    "ref": ref,
                    "alt": allele,
                    "gene": info_dict.get("GENE", "UNKNOWN"),
                    "hgvs": info_dict.get("HGVS_C"),
                    "mutation_type": info_dict.get("SO", "unknown"),
                    "clinvar_id": info_dict.get("CLINVAR_ID"),
                    "cosmic_id": info_dict.get("COSMIC_ID"),
                    "filter_status": filter_status or "PASS",
                    "filter_passed": passed,
                    "vaf": vaf,
                    "depth": depth,
                })

    return mutations


def _upload_vcf_to_minio(vcf_path: str, patient_id: str, submission_id: str) -> str:
    """Upload processed VCF to the vcf bucket. Returns S3 key."""
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    from config import settings

    scheme = "https" if settings.minio_secure else "http"
    s3 = boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    try:
        s3.head_bucket(Bucket=settings.bucket_vcf)
    except ClientError:
        s3.create_bucket(Bucket=settings.bucket_vcf)

    key = f"{patient_id}/{submission_id}/annotated.vcf"
    s3.upload_file(
        vcf_path,
        settings.bucket_vcf,
        key,
        ExtraArgs={"ServerSideEncryption": "AES256"},
    )
    return key


# ── Periodic maintenance tasks (invoked by Celery Beat) ───────────────────────

@celery_app.task(
    name="workers.genomic_worker.sweep_stale_submissions",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def sweep_stale_submissions(self):
    """Re-queue or fail submissions that have been stuck in 'processing' > 6 hours."""
    from datetime import datetime, timedelta, UTC
    from sqlalchemy import select
    from workers._db_sync import get_sync_session
    from models.submission import Submission, SubmissionStatus

    cutoff = datetime.now(UTC) - timedelta(hours=6)
    with get_sync_session() as db:
        stale = db.execute(
            select(Submission).where(
                Submission.status == SubmissionStatus.processing,
                Submission.created_at < cutoff,
            )
        ).scalars().all()
        for s in stale:
            s.status = SubmissionStatus.failed
            logger.warning("[genomic] Swept stale submission %s (stuck since %s)", s.id, s.created_at)
        db.commit()
    logger.info("[genomic] Swept %d stale submissions", len(stale))

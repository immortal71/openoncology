"""
Genomic Worker — runs the Nextflow bioinformatics pipeline on patient DNA files.

Pipeline steps:
  1. Download DNA file from MinIO
  2. Run Nextflow: FastQC → Trimmomatic → BWA-MEM2 → GATK → OpenCRAVAT
  3. Parse VCF output — extract mutations
  4. Store mutations in DB, update submission status
  5. Queue AI worker for classification + repurposing
"""
import subprocess
import tempfile
import os
import logging
from datetime import datetime

from workers import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.genomic_worker.run_genomic_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
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
    """
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


def _parse_and_annotate_vcf(vcf_path: str) -> list[dict]:
    """
    Parse the OpenCRAVAT-annotated VCF file.
    Returns a list of mutation dicts with gene, hgvs, clinvar, cosmic etc.
    """
    mutations = []
    with open(vcf_path, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, vid, ref, alt, qual, filt, info = parts[:8]

            # Parse INFO field for OpenCRAVAT annotations
            info_dict = dict(
                kv.split("=", 1) if "=" in kv else (kv, "true")
                for kv in info.split(";")
            )

            mutations.append({
                "chrom": chrom,
                "pos": int(pos) if pos.isdigit() else None,
                "ref": ref,
                "alt": alt,
                "gene": info_dict.get("GENE", "UNKNOWN"),
                "hgvs": info_dict.get("HGVS_C"),
                "mutation_type": info_dict.get("SO", "unknown"),
                "clinvar_id": info_dict.get("CLINVAR_ID"),
                "cosmic_id": info_dict.get("COSMIC_ID"),
            })

    return mutations


def _upload_vcf_to_minio(vcf_path: str, patient_id: str, submission_id: str) -> str:
    """Upload processed VCF to the vcf bucket. Returns S3 key."""
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
    key = f"{patient_id}/{submission_id}/annotated.vcf"
    s3.upload_file(
        vcf_path,
        settings.bucket_vcf,
        key,
        ExtraArgs={"ServerSideEncryption": "AES256"},
    )
    return key

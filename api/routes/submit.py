"""
Submit route — receives patient biopsy PDF + DNA file, queues genomic pipeline.
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.patient import Patient
from models.submission import Submission, SubmissionStatus
from services.storage import upload_encrypted_file
from workers.genomic_worker import run_genomic_pipeline
from routes.auth import get_current_patient
from middleware.rate_limit import limiter, READ_LIMIT, UPLOAD_LIMIT
from schemas import SubmissionResponse, SubmissionStatusOut
from utils.http import not_found_error, validation_error

router = APIRouter(prefix="/api/submit", tags=["submit"])

ALLOWED_BIOPSY_TYPES = {"application/pdf", "image/jpeg", "image/png"}
ALLOWED_DNA_TYPES = {
    "text/plain",               # VCF / FASTQ plain text
    "application/gzip",         # FASTQ.gz / VCF.gz
    "application/octet-stream", # BAM / binary VCF
}
ALLOWED_BIOPSY_EXT = {"pdf", "jpg", "jpeg", "png", "txt", "doc", "docx", "rtf", "xml", "json"}
ALLOWED_DNA_EXT = {"vcf", "fastq", "fq", "bam", "gz", "txt", "csv", "tsv", "xml", "json"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

_FASTQ_SUFFIXES = (".fastq", ".fq", ".fastq.gz", ".fq.gz")


def _is_fastq_name(name: str | None) -> bool:
    """Mirrors _is_fastq_name in pipeline/main.nf. The two decide the same thing
    about the same file at different ends of the system, so they agree on the
    suffix list deliberately."""
    return (name or "").lower().endswith(_FASTQ_SUFFIXES)


@router.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=SubmissionResponse)
@limiter.limit(UPLOAD_LIMIT)
async def submit_sample(
    request: Request,
    biopsy_file: UploadFile = File(..., description="Biopsy PDF or image"),
    dna_file: UploadFile = File(
        ...,
        description="DNA file: VCF, BAM, or mate 1 of a FASTQ pair",
    ),
    dna_file_r2: UploadFile | None = File(
        None,
        description=(
            "Mate 2 of a paired-end FASTQ sample. Omit for single-end reads, "
            "VCF or BAM. Sequencers emit paired-end reads as two files and both "
            "are needed: aligning one mate alone discards the insert-size "
            "information that places reads in repetitive regions."
        ),
    ),
    cancer_type: str = Form(..., max_length=128),
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    keycloak_id = token_payload.get("sub")

    # Look up or create patient record
    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()

    if not patient:
        raise not_found_error(request, "Patient profile not found. Please complete registration.")

    # Validate file types with extension fallback for browsers that send generic MIME
    biopsy_ext = (biopsy_file.filename or "").split(".")[-1].lower()
    dna_ext = (dna_file.filename or "").split(".")[-1].lower()

    biopsy_ok = (biopsy_file.content_type in ALLOWED_BIOPSY_TYPES) or (biopsy_ext in ALLOWED_BIOPSY_EXT)
    dna_ok = (dna_file.content_type in ALLOWED_DNA_TYPES) or (dna_ext in ALLOWED_DNA_EXT)

    if not biopsy_ok:
        raise validation_error(request, f"Biopsy file type '{biopsy_file.content_type}' not supported.")
    if not dna_ok:
        raise validation_error(request, f"DNA file type '{dna_file.content_type}' not supported.")

    # A mate 2 is only meaningful for FASTQ, and sending one alongside a VCF or a
    # BAM means the caller has misunderstood what they are uploading. Rejecting
    # is better than accepting and ignoring it, which would look like it worked.
    dna_r2_key = None
    if dna_file_r2 is not None and dna_file_r2.filename:
        r2_ext = (dna_file_r2.filename or "").split(".")[-1].lower()
        r2_ok = (dna_file_r2.content_type in ALLOWED_DNA_TYPES) or (r2_ext in ALLOWED_DNA_EXT)
        if not r2_ok:
            raise validation_error(
                request, f"Mate 2 file type '{dna_file_r2.content_type}' not supported."
            )
        if not _is_fastq_name(dna_file.filename) or not _is_fastq_name(dna_file_r2.filename):
            raise validation_error(
                request,
                "A second read file is only accepted for paired-end FASTQ. "
                "VCF and BAM submissions carry no mate.",
            )

    # Upload to encrypted MinIO/S3 storage
    biopsy_key = await upload_encrypted_file(
        file=biopsy_file,
        patient_id=patient.id,
        file_type="biopsy",
    )
    dna_key = await upload_encrypted_file(
        file=dna_file,
        patient_id=patient.id,
        file_type="dna",
    )
    if dna_file_r2 is not None and dna_file_r2.filename:
        dna_r2_key = await upload_encrypted_file(
            file=dna_file_r2,
            patient_id=patient.id,
            file_type="dna",
        )

    # Create submission record
    submission = Submission(
        patient_id=patient.id,
        cancer_type=cancer_type,
        status=SubmissionStatus.queued,
        biopsy_s3_key=biopsy_key,
        dna_s3_key=dna_key,
        dna_r2_s3_key=dna_r2_key,
    )
    db.add(submission)
    await db.flush()  # get submission.id before commit

    # Queue genomic pipeline background job
    job = run_genomic_pipeline.apply_async(
        args=[submission.id, patient.id, biopsy_key, dna_key, cancer_type, dna_r2_key],
        queue="genomic",
    )
    submission.pipeline_job_id = job.id
    await db.commit()

    return {
        "status": "queued",
        "submission_id": submission.id,
        "job_id": job.id,
        "message": "Your sample is being processed. We'll notify you when results are ready.",
    }


@router.get("/{submission_id}/status", response_model=SubmissionStatusOut)
@limiter.limit(READ_LIMIT)
async def get_submission_status(
    request: Request,
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    keycloak_id = token_payload.get("sub")
    submission = (await db.execute(
        select(Submission)
        .join(Patient)
        .where(
            Submission.id == submission_id,
            Patient.keycloak_id == keycloak_id,
        )
    )).scalar_one_or_none()

    if not submission:
        raise not_found_error(request, "Submission not found.")

    return {
        "submission_id": submission.id,
        "status": submission.status,
        "cancer_type": submission.cancer_type,
        "submitted_at": submission.submitted_at,
        "completed_at": submission.completed_at,
    }

"""
Submit route — receives patient biopsy PDF + DNA file, queues genomic pipeline.
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.patient import Patient
from models.submission import Submission, SubmissionStatus
from services.storage import upload_encrypted_file
from workers.genomic_worker import run_genomic_pipeline
from routes.auth import get_current_patient
from middleware.rate_limit import limiter, READ_LIMIT, UPLOAD_LIMIT

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


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(UPLOAD_LIMIT)
async def submit_sample(
    request: Request,
    biopsy_file: UploadFile = File(..., description="Biopsy PDF or image"),
    dna_file: UploadFile = File(..., description="DNA file: VCF, FASTQ, or BAM"),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found. Please complete registration.",
        )

    # Validate file types with extension fallback for browsers that send generic MIME
    biopsy_ext = (biopsy_file.filename or "").split(".")[-1].lower()
    dna_ext = (dna_file.filename or "").split(".")[-1].lower()

    biopsy_ok = (biopsy_file.content_type in ALLOWED_BIOPSY_TYPES) or (biopsy_ext in ALLOWED_BIOPSY_EXT)
    dna_ok = (dna_file.content_type in ALLOWED_DNA_TYPES) or (dna_ext in ALLOWED_DNA_EXT)

    if not biopsy_ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Biopsy file type '{biopsy_file.content_type}' not supported.",
        )
    if not dna_ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"DNA file type '{dna_file.content_type}' not supported.",
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

    # Create submission record
    submission = Submission(
        patient_id=patient.id,
        cancer_type=cancer_type,
        status=SubmissionStatus.queued,
        biopsy_s3_key=biopsy_key,
        dna_s3_key=dna_key,
    )
    db.add(submission)
    await db.flush()  # get submission.id before commit

    # Queue genomic pipeline background job
    job = run_genomic_pipeline.apply_async(
        args=[submission.id, patient.id, biopsy_key, dna_key, cancer_type],
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


@router.get("/{submission_id}/status")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    return {
        "submission_id": submission.id,
        "status": submission.status,
        "cancer_type": submission.cancer_type,
        "submitted_at": submission.submitted_at,
        "completed_at": submission.completed_at,
    }

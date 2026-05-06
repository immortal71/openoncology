"""FHIR R4 export routes.

Endpoints:
  GET /api/fhir/DiagnosticReport/{submission_id}
      Returns an HL7 FHIR R4 DiagnosticReport resource for the patient's
      genomic analysis result.

  GET /api/fhir/Observation/{mutation_id}
      Returns an HL7 FHIR R4 Observation resource (Variant profile) for
      a single somatic mutation.

Both endpoints are authenticated (patient token required) to ensure only
authorised patients and clinicians can export PHI as FHIR resources.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.mutation import Mutation
from models.patient import Patient
from models.submission import Submission
from routes.auth import get_current_patient
from services.fhir_export import build_diagnostic_report, build_observation

router = APIRouter(prefix="/api/fhir", tags=["fhir"])

# FHIR JSON content type per R4 spec §2.6.6
_FHIR_CONTENT_TYPE = "application/fhir+json; fhirVersion=4.0"


@router.get("/DiagnosticReport/{submission_id}", response_class=JSONResponse)
async def get_diagnostic_report(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return a FHIR R4 DiagnosticReport for a submission.

    The report includes references to all Observation resources (mutations)
    and a conclusion derived from the AI analysis summary.
    """
    keycloak_id = token_payload.get("sub")

    submission = (await db.execute(
        select(Submission)
        .join(Patient)
        .where(
            Submission.id == submission_id,
            Patient.keycloak_id == keycloak_id,
        )
        .options(selectinload(Submission.mutations), selectinload(Submission.result))
    )).scalar_one_or_none()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found or access denied.",
        )

    patient = (await db.execute(
        select(Patient).where(Patient.keycloak_id == keycloak_id)
    )).scalar_one_or_none()

    patient_fhir_ref = f"Patient/{patient.id}" if patient else "Patient/unknown"

    report = build_diagnostic_report(
        submission=submission,
        result=submission.result,
        mutations=submission.mutations,
        patient_id_fhir=patient_fhir_ref,
    )

    return JSONResponse(
        content=report,
        headers={"Content-Type": _FHIR_CONTENT_TYPE},
    )


@router.get("/Observation/{mutation_id}", response_class=JSONResponse)
async def get_observation(
    mutation_id: str,
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(get_current_patient),
):
    """Return a FHIR R4 Observation resource (Variant profile) for a mutation.

    Verifies that the mutation belongs to the authenticated patient's submission.
    """
    keycloak_id = token_payload.get("sub")

    mutation = (await db.execute(
        select(Mutation)
        .join(Submission)
        .join(Patient)
        .where(
            Mutation.id == mutation_id,
            Patient.keycloak_id == keycloak_id,
        )
    )).scalar_one_or_none()

    if not mutation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mutation not found or access denied.",
        )

    observation = build_observation(mutation)

    return JSONResponse(
        content=observation,
        headers={"Content-Type": _FHIR_CONTENT_TYPE},
    )

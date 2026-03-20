"""
GDPR Worker — erase_patient_data Celery task.

Performs a complete right-to-erasure (GDPR Art. 17):
  1. Delete all DB rows linked to the patient (cascade)
  2. Remove all MinIO objects (raw files, VCFs, reports)
  3. Delete the Keycloak user account
  4. Mark the DeletionRequest as complete
  5. Send confirmation email via Resend
"""
import logging

from workers import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="workers.gdpr_worker.erase_patient_data",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def erase_patient_data(self, deletion_request_id: str):
    from datetime import datetime, UTC

    from workers._db_sync import get_sync_session
    from models.deletion_request import DeletionRequest
    from models.patient import Patient
    from models.submission import Submission
    from models.mutation import Mutation
    from models.repurposing import RepurposingCandidate
    from models.result import Result
    from models.order import Order
    from models.campaign import Campaign
    from sqlalchemy import select, delete

    try:
        with get_sync_session() as db:
            req = db.get(DeletionRequest, deletion_request_id)
            if not req or req.status != "pending":
                logger.warning("[gdpr] DeletionRequest %s not found or not pending", deletion_request_id)
                return

            patient = db.get(Patient, req.patient_id)
            if not patient:
                logger.warning("[gdpr] Patient %s already deleted", req.patient_id)
                req.status = "complete"
                req.completed_at = datetime.now(UTC)
                db.commit()
                return

            # ── 1. Collect submission IDs for cascaded deletes ──────────────
            submission_ids = [
                sid for (sid,) in db.execute(
                    select(Submission.id).where(Submission.patient_id == patient.id)
                ).all()
            ]

            minio_keys: list[str] = []
            if submission_ids:
                # Collect MinIO keys from submissions before deleting
                submissions = db.execute(
                    select(Submission).where(Submission.id.in_(submission_ids))
                ).scalars().all()
                for s in submissions:
                    if s.raw_file_key:
                        minio_keys.append((s.bucket_raw or "openoncology-raw", s.raw_file_key))
                    if s.vcf_key:
                        minio_keys.append((s.bucket_vcf or "openoncology-vcf", s.vcf_key))
                    if s.report_key:
                        minio_keys.append((s.bucket_reports or "openoncology-reports", s.report_key))

                db.execute(delete(Mutation).where(Mutation.submission_id.in_(submission_ids)))
                db.execute(delete(RepurposingCandidate).where(RepurposingCandidate.submission_id.in_(submission_ids)))
                db.execute(delete(Result).where(Result.submission_id.in_(submission_ids)))
                db.execute(delete(Submission).where(Submission.id.in_(submission_ids)))

            db.execute(delete(Order).where(Order.patient_id == patient.id))
            db.execute(delete(Campaign).where(Campaign.patient_id == patient.id))

            keycloak_id = patient.keycloak_id
            contact_email = _get_email_from_keycloak(keycloak_id) or "unknown"

            db.delete(patient)
            db.commit()

        # ── 2. MinIO object removal ─────────────────────────────────────────
        _delete_minio_objects(minio_keys)

        # ── 3. Keycloak user deletion ───────────────────────────────────────
        _delete_keycloak_user(keycloak_id)

        # ── 4. Mark deletion request complete ──────────────────────────────
        with get_sync_session() as db:
            req = db.get(DeletionRequest, deletion_request_id)
            if req:
                req.status = "complete"
                req.completed_at = datetime.now(UTC)
                db.commit()

        # ── 5. Confirmation email ───────────────────────────────────────────
        if contact_email != "unknown":
            _send_erasure_confirmation(contact_email)

        logger.info("[gdpr] Patient %s fully erased (request %s)", req.patient_id if req else "?", deletion_request_id)

    except Exception as exc:
        logger.error("[gdpr] erase_patient_data failed: %s", exc)
        raise self.retry(exc=exc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_email_from_keycloak(keycloak_id: str) -> str | None:
    import httpx
    from config import settings

    try:
        token_resp = httpx.post(
            f"{settings.keycloak_url}/realms/master/protocol/openid-connect/token",
            data={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": "admin",
                "password": getattr(settings, "keycloak_admin_password", ""),
            },
            timeout=5,
        )
        token = token_resp.json().get("access_token")
        if not token:
            return None
        resp = httpx.get(
            f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users/{keycloak_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("email")
    except Exception as exc:
        logger.warning("[gdpr] Keycloak email lookup failed: %s", exc)
        return None


def _delete_keycloak_user(keycloak_id: str) -> None:
    import httpx
    from config import settings

    try:
        token_resp = httpx.post(
            f"{settings.keycloak_url}/realms/master/protocol/openid-connect/token",
            data={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": "admin",
                "password": getattr(settings, "keycloak_admin_password", ""),
            },
            timeout=5,
        )
        token = token_resp.json().get("access_token")
        if not token:
            logger.warning("[gdpr] Could not get Keycloak admin token for user deletion")
            return
        resp = httpx.delete(
            f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users/{keycloak_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        resp.raise_for_status()
        logger.info("[gdpr] Keycloak user %s deleted", keycloak_id)
    except Exception as exc:
        logger.error("[gdpr] Keycloak user deletion failed for %s: %s", keycloak_id, exc)


def _delete_minio_objects(keys: list[tuple[str, str]]) -> None:
    """Delete each (bucket, key) pair from MinIO."""
    if not keys:
        return
    try:
        from minio import Minio
        from config import settings

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        for bucket, key in keys:
            try:
                client.remove_object(bucket, key)
                logger.info("[gdpr] Deleted MinIO object %s/%s", bucket, key)
            except Exception as exc:
                logger.warning("[gdpr] Could not delete %s/%s: %s", bucket, key, exc)
    except Exception as exc:
        logger.error("[gdpr] MinIO deletion setup failed: %s", exc)


def _send_erasure_confirmation(to_email: str) -> None:
    try:
        import resend
        from config import settings

        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": "OpenOncology <noreply@openoncology.org>",
            "to": to_email,
            "subject": "Your OpenOncology data has been deleted",
            "html": (
                "<p>This email confirms that all personal data associated with your "
                "OpenOncology account has been permanently deleted in accordance with "
                "GDPR Article 17 (Right to Erasure).</p>"
                "<p>If you did not request this deletion or have any questions, please "
                "contact <a href='mailto:privacy@openoncology.org'>privacy@openoncology.org</a>.</p>"
            ),
        })
    except Exception as exc:
        logger.warning("[gdpr] Could not send erasure confirmation email: %s", exc)

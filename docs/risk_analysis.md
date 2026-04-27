# Risk Analysis

This is the current technical risk analysis placeholder referenced by the HIPAA checklist.

## Scope
- API authentication and authorization boundaries
- PHI data flows (upload, storage, access, deletion)
- Third-party integrations (Stripe, Keycloak, Resend, external genomic sources)
- Infrastructure controls (networking, logging, backups, disaster recovery)

## Current Known Risks
- Inconsistent schema/version drift can break protected workflows and auditability.
- Missing or weak route-level controls (rate limits and role checks) can increase abuse risk.
- External dependency failures (OncoKB, Stripe, Keycloak) can impact clinical workflow continuity.

## Existing Mitigations
- Structured PHI access logging middleware
- Keycloak-based JWT auth and role extraction
- Redis-backed limiter infrastructure available
- Security scan workflows in CI (dependency + SAST + DAST + image scan)

## Open Actions
- Finalize formal risk register with likelihood/impact scoring per control.
- Add quarterly review schedule and documented owner sign-off.
- Verify audit log retention and immutability policy in deployment environment.
- Validate migration drift checks in CI before deployment.

## Review Cadence
- Baseline: quarterly
- Triggered review: after major architecture or compliance-impacting changes

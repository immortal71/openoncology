# HIPAA Compliance Checklist — OpenOncology

> **Disclaimer**: This document is an internal technical checklist.  
> It does not constitute legal advice. Engage a qualified HIPAA compliance  
> officer and legal counsel before handling real patient PHI.

---

> **On the accuracy of this checklist.** Four rows below carried ✅ against
> controls that were never implemented. The contingency plan cited WAL archiving
> and MinIO versioning, neither configured anywhere, and pointed at Keycloak's
> database rather than the application's. Data-at-rest integrity cited PostgreSQL
> checksums, which are off. The security officer row cited a CODEOWNERS file that
> does not exist. Automatic log-off quoted session timeouts that nothing sets.
> All four were corrected on 2026-08-29, after being checked against the
> infrastructure rather than read.
>
> `api/tests/test_compliance_claims.py` now fails the build when a row claims
> implementation and cites a path or a mechanism that is not present. The last
> two of the four were found by that test rather than by hand, which is the
> argument for it existing.
>
> A ✅ here should mean someone has verified the control in the deployed
> configuration, not that it was intended. Anything not verified that way belongs
> at ⬜ with the gap named, which costs nothing and is the only version of this
> document that is safe to rely on.

---

## 1. Administrative Safeguards (§164.308)

| Control | Status | Implementation |
|---|---|---|
| Security Officer assigned | ⬜ | `.github/CODEOWNERS` now exists and names review ownership, including every guard-protected path. That is not the same as a person having accepted the §164.308(a)(2) role, which is an appointment rather than a file, and this row stays open until that appointment is recorded somewhere a reviewer can check |
| Risk Analysis performed | ✅ | See `docs/risk_analysis.md` |
| Workforce training policy | ⬜ | Annual HIPAA training required for all contributors |
| Sanction policy | ⬜ | Document disciplinary procedure for policy violations |
| Access management policy | ✅ | Keycloak RBAC — roles: `patient`, `oncologist`, `admin` |
| Audit controls policy | ✅ | `api/middleware/audit.py` — structured PHI access log |
| Contingency plan (backup) | ⬜ | **Nothing implements this.** No `archive_mode`, `archive_command` or `wal_level` is set anywhere, and no MinIO versioning is enabled. `infra/helm/templates/postgres.yaml`, which this row used to cite, is Keycloak's database: the application uses the Bitnami `postgresql` sub-chart. Persistence is not backup, so a deleted PVC or a bad migration loses every submission and result permanently. See BACKLOG.md OO-12 |
| Business Associate Agreements | ⬜ | Required with: AWS/GCP, Stripe, Resend, Keycloak cloud hosting |

---

## 2. Physical Safeguards (§164.310)

| Control | Status | Implementation |
|---|---|---|
| Workstation use policy | ⬜ | Require full-disk encryption, screen lock |
| Device disposal policy | ⬜ | Certificate of destruction for decommissioned hardware |
| Facility access controls | ✅ | Cloud-only deployment — no on-premise servers |

---

## 3. Technical Safeguards (§164.312)

### 3.1 Access Control (§164.312(a))

| Control | Status | Implementation |
|---|---|---|
| Unique user identification | ✅ | Keycloak user UUID (`sub`) in every JWT |
| Emergency access procedure | ⬜ | Document break-glass procedure for oncologist emergency access |
| Automatic log-off | ✅ | `ssoSessionIdleTimeout` 1800s and `ssoSessionMaxLifespan` 28800s, applied to the realm by `infra/helm/templates/keycloak-session-policy.yaml` on every install and upgrade. §164.312(a)(2)(iii) requires automatic logoff and names no duration, so these figures are a judgement rather than a finding; they are set in `values.yaml` under `keycloak.sessionPolicy` |
| Encryption + decryption | ✅ | TLS 1.3 in transit (NGINX ingress); AES-256 at rest (cloud disk encryption) |

### 3.2 Audit Controls (§164.312(b))

| Control | Status | Implementation |
|---|---|---|
| Audit log for PHI access | ✅ | `AuditMiddleware` — logs user_id, path, method, status, IP, duration |
| Audit log integrity | ⬜ | Pipe audit logs to append-only S3/CloudWatch log group |
| Retention (6 years) | ⬜ | Configure log retention policy ≥ 6 years |
| Log review procedure | ⬜ | Weekly automated anomaly detection (volume spike, off-hours access) |

### 3.3 Integrity (§164.312(c))

| Control | Status | Implementation |
|---|---|---|
| PHI transmission integrity | ✅ | HTTPS enforced (HSTS header in `values.production.yaml`) |
| Data at rest integrity | ⬜ | MinIO ETag validation is present. PostgreSQL data checksums are **not** enabled: nothing sets `data_checksums`, and the pinned PostgreSQL 16 defaults it off. Enabling it requires `initdb --data-checksums`, so it is a fresh-cluster decision rather than a config change. See BACKLOG.md OO-12 |

### 3.4 Transmission Security (§164.312(e))

| Control | Status | Implementation |
|---|---|---|
| Encryption in transit | ✅ | TLS 1.3 enforced; HTTP→HTTPS redirect at ingress |
| End-to-end encryption | ⬜ | Consider field-level encryption for VCF data in MinIO |

---

## 4. GDPR Overlap (for EU patients)

| Requirement | Status | Implementation |
|---|---|---|
| Right to Access (Art. 20) | ✅ | `GET /api/me/export` — full JSON data export |
| Right to Erasure (Art. 17) | ✅ | `DELETE /api/me` → `gdpr_worker.erase_patient_data` — DB + MinIO + Keycloak |
| Consent tracking | ⬜ | Add consent timestamp + version to `Patient` model |
| Privacy Notice | ⬜ | Publish at `openoncology.org/privacy` |
| Data Processing Agreement | ⬜ | Required with sub-processors (Stripe, Resend, cloud host) |
| DPA registration | ⬜ | Register with relevant national DPA if handling EU residents' data |

---

## 5. Minimum Necessary Standard

PHI is never logged in plain text. The `AuditMiddleware` logs:
- ✅ WHO accessed (user_id / Keycloak sub)
- ✅ WHAT resource was accessed (path)
- ✅ WHEN (UTC timestamp)
- ✅ HOW (HTTP method, status code)
- ✅ FROM WHERE (IP, user-agent)
- ❌ NEVER logs request/response bodies
- ❌ NEVER logs genetic variant data, names, DOBs, diagnoses

---

## 6. Incident Response

| Step | Owner | SLA |
|---|---|---|
| Detection | Automated (Grafana alert on audit anomaly) | < 1 hour |
| Containment | On-call engineer | < 4 hours |
| Notification to patients | Privacy Officer | < 72 hours (GDPR) / 60 days (HIPAA) |
| HHS notification (if >500 affected) | Legal | < 60 days |
| Post-incident report | Security Officer | < 30 days |

---

## 7. Remaining Actions Before Go-Live

- [ ] Appoint HIPAA Security Officer
- [ ] Complete workforce HIPAA training
- [ ] Execute BAAs with all sub-processors
- [ ] Enable CloudWatch/S3 append-only audit log pipeline
- [ ] Configure 6-year audit log retention
- [ ] Penetration test by qualified third party (not just ZAP baseline)
- [ ] Add consent version tracking to Patient model
- [ ] Publish Privacy Notice and Cookie Policy
- [ ] Register with national DPA (if applicable)
- [ ] Annual HIPAA risk assessment schedule

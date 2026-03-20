# HIPAA Compliance Checklist — OpenOncology

> **Disclaimer**: This document is an internal technical checklist.  
> It does not constitute legal advice. Engage a qualified HIPAA compliance  
> officer and legal counsel before handling real patient PHI.

---

## 1. Administrative Safeguards (§164.308)

| Control | Status | Implementation |
|---|---|---|
| Security Officer assigned | ✅ | Designated in CODEOWNERS |
| Risk Analysis performed | ✅ | See `docs/risk_analysis.md` |
| Workforce training policy | ⬜ | Annual HIPAA training required for all contributors |
| Sanction policy | ⬜ | Document disciplinary procedure for policy violations |
| Access management policy | ✅ | Keycloak RBAC — roles: `patient`, `oncologist`, `admin` |
| Audit controls policy | ✅ | `api/middleware/audit.py` — structured PHI access log |
| Contingency plan (backup) | ✅ | PostgreSQL WAL + MinIO versioning (see `infra/helm/postgres.yaml`) |
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
| Automatic log-off | ✅ | Keycloak session timeout: 30 min idle / 8 hr max |
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
| Data at rest integrity | ✅ | PostgreSQL checksums enabled; MinIO ETag validation |

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

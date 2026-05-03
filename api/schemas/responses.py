from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SubmissionResponse(BaseModel):
    status: str
    submission_id: str
    job_id: Optional[str] = None
    message: Optional[str] = None


class SubmissionStatusOut(BaseModel):
    submission_id: str
    status: str
    cancer_type: Optional[str] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MutationOut(BaseModel):
    gene: Optional[str] = None
    mutation_type: Optional[str] = None
    hgvs: Optional[str] = None
    classification: Optional[str] = None
    oncokb_level: Optional[str] = None
    is_targetable: bool = False
    alphamissense_score: Optional[float] = None


class DrugCandidateOut(BaseModel):
    drug_name: str
    oncokb_level: Optional[str] = None
    rank_score: Optional[float] = None
    confidence_level: Optional[str] = None
    approval_status: Optional[str] = None
    evidence_completeness: Optional[float] = None


class OncologistReportOut(BaseModel):
    executive_summary: dict[str, Any] = Field(default_factory=dict)
    sample_quality: Optional[dict[str, Any]] = None
    genomic_alterations: list[dict[str, Any]] = Field(default_factory=list)
    drug_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    experimental_candidates: list[dict[str, Any]] = Field(default_factory=list)
    audit_trail: dict[str, Any] = Field(default_factory=dict)
    withdrawn_warnings: list[dict[str, Any]] = Field(default_factory=list)
    system_limitations: list[str] = Field(default_factory=list)
    tier_gap_explanation: list[str] = Field(default_factory=list)
    disclaimer: Optional[str] = None
    plain_text: Optional[str] = None


class ResultsResponse(BaseModel):
    submission_id: str
    cancer_type: Optional[str] = None
    status: str
    message: Optional[str] = None
    has_targetable_mutation: bool = False
    target_gene: Optional[str] = None
    summary: Optional[str] = None
    patient_summary: Optional[dict[str, Any]] = None
    patient_summary_text: Optional[str] = None
    plain_language_summary: Optional[str] = None
    cbioportal_data: Optional[Any] = None
    cosmic_sample_count: Optional[str] = None
    oncologist_reviewed: bool = False
    oncologist_notes: Optional[str] = None
    custom_drug_possible: bool = False
    custom_drug_reason: Optional[str] = None
    oncologist_report: Optional[OncologistReportOut] = None
    mutations: list[MutationOut] = Field(default_factory=list)
    result_id: Optional[str] = None

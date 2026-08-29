"""
Paired-end reads survive from upload to aligner.

BACKLOG.md OO-10. Every sequencer emits paired-end reads as two files, and the
system took one. `POST /api/submit` accepted a single `dna_file` documented as
"VCF, FASTQ, or BAM"; `main.nf` channelled it with `fromPath` rather than
`fromFilePairs`; `trimmomatic.nf` ran `trimmomatic SE`; `bwa_mem2.nf` handed one
file to `bwa-mem2 mem`. A clinician holding R1 and R2 could upload one of them,
nothing said what had happened, and the sample was aligned without the
insert-size information that places reads in repetitive regions. It was then
reported with the same confidence as any other result.

The pipeline assertions are made by reading the Nextflow source, the same way
`test_pipeline_config.py` does, because CI has no `nextflow` and because the
properties asserted are properties of the files. They are weaker than running
the pipeline and they are what is available; the runbook in
`docs/RUNBOOK_VARIANT_CALLING_VALIDATION.md` is where the real thing gets run.
"""
import io
import re
from pathlib import Path

import pytest
from httpx import AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "pipeline"
MAIN_NF = (PIPELINE / "main.nf").read_text(encoding="utf-8")
TRIMMOMATIC_NF = (PIPELINE / "modules" / "trimmomatic.nf").read_text(encoding="utf-8")
BWA_NF = (PIPELINE / "modules" / "bwa_mem2.nf").read_text(encoding="utf-8")
FASTQC_NF = (PIPELINE / "modules" / "fastqc.nf").read_text(encoding="utf-8")


# ── The pipeline can express a pair at all ───────────────────────────────────

def test_main_accepts_a_second_mate():
    assert "params.reads_r2" in MAIN_NF


def test_reads_travel_as_one_item_per_sample():
    """
    The defect was structural rather than a missing flag. `fromPath` emits one
    item per file, so a two-file sample became two independent workflow runs.
    Reads are now tupled with a sample id so a pair stays one item.
    """
    assert "reads_ch" in MAIN_NF
    assert re.search(r"tuple\(\s*\n?\s*_sample_id_from_reads", MAIN_NF) or \
           "tuple(_sample_id_from_reads" in MAIN_NF


@pytest.mark.parametrize(
    "module,name",
    [(TRIMMOMATIC_NF, "trimmomatic"), (BWA_NF, "bwa_mem2"), (FASTQC_NF, "fastqc")],
)
def test_fastq_modules_take_the_sample_tuple(module, name):
    assert "tuple val(sample_id), path(reads)" in module, (
        f"{name} still takes a bare path, so it cannot receive both mates"
    )


def test_sample_id_strips_the_mate_marker():
    """
    R1 and R2 of one sample must resolve to the same id. Without stripping the
    marker the pair would be named after mate 1 and every output would read as
    though mate 2 were a different sample.
    """
    helper = MAIN_NF[MAIN_NF.index("def _sample_id_from_reads") :]
    helper = helper[: helper.index("\n}")]
    assert "replaceAll" in helper
    assert "R?[12]" in helper


# ── Trimming keeps the mates in step ─────────────────────────────────────────

def test_trimmomatic_runs_pe_for_a_pair():
    assert "trimmomatic PE" in TRIMMOMATIC_NF


def test_trimmomatic_keeps_the_single_end_path():
    """Single-end input is still valid input; it was never the bug."""
    assert "trimmomatic SE" in TRIMMOMATIC_NF


def test_paired_trimming_uses_paired_adapters():
    """
    TruSeq3-SE against paired reads leaves the adapter read-through that PE mode
    is specifically able to find, so the adapter file follows the mode.
    """
    assert "params.adapters_pe" in TRIMMOMATIC_NF
    assert "params.adapters_se" in TRIMMOMATIC_NF
    assert "adapters_pe" in MAIN_NF and "adapters_se" in MAIN_NF


def test_unpaired_survivors_are_emitted_not_silently_dropped():
    """
    Trimmomatic PE writes four files. The two unpaired ones are reads whose mate
    was discarded. They are published so the loss is countable, and deliberately
    not fed to the aligner.
    """
    assert "emit: unpaired" in TRIMMOMATIC_NF
    assert "1U" in TRIMMOMATIC_NF and "2U" in TRIMMOMATIC_NF


def test_only_paired_output_reaches_the_aligner():
    aligner_input = MAIN_NF[MAIN_NF.index("trimmed_ch"):]
    assert "TRIMMOMATIC.out.unpaired" not in aligner_input


# ── Alignment receives both mates ────────────────────────────────────────────

def test_bwa_receives_every_read_file():
    """
    One `bwa-mem2 mem` invocation with both mates. Aligning them separately, or
    passing only the first, discards the insert-size distribution, which is most
    of the value of paired-end sequencing.
    """
    assert "read_args" in BWA_NF
    assert "reads.join(' ')" in BWA_NF
    assert re.search(r"bwa-mem2 mem[\s\S]{0,220}\$\{read_args\}", BWA_NF)


def test_alignment_produces_one_bam_per_sample():
    """A pair is one sample, so it is one BAM. Everything downstream assumes it."""
    assert 'path "${sample_id}.sorted.bam",     emit: bam' in BWA_NF
    assert BWA_NF.count("emit: bam") == 1


def test_read_group_carries_the_sample_id():
    """`SM:patient` was a constant, so every BAM claimed the same sample."""
    assert "SM:${sample_id}" in BWA_NF
    assert "SM:patient" not in BWA_NF


# ── A mate is only meaningful for FASTQ ──────────────────────────────────────

def test_main_rejects_a_mate_alongside_non_fastq_input():
    assert "only meaningful with FASTQ" in MAIN_NF


def test_main_rejects_a_missing_mate_file():
    assert "Missing mate 2 file" in MAIN_NF


# ── Intake: the mate can actually be uploaded ────────────────────────────────
#
# These drive the real route rather than reading source. Storage and Celery are
# mocked the same way TestSubmitEndpoint does it.


def _mock_storage_and_queue(monkeypatch) -> dict:
    """Capture what the route stored and what it enqueued."""
    captured: dict = {"uploads": [], "job_args": None}

    async def _fake_upload(**kwargs):
        key = f"mock/{kwargs['file_type']}-{len(captured['uploads'])}.bin"
        captured["uploads"].append(kwargs["file"].filename)
        return key

    class _FakeJob:
        id = "celery-job-id-test"

    def _fake_apply_async(args, queue):
        captured["job_args"] = args
        return _FakeJob()

    monkeypatch.setattr("routes.submit.upload_encrypted_file", _fake_upload)
    monkeypatch.setattr("routes.submit.run_genomic_pipeline.apply_async", _fake_apply_async)
    return captured


async def test_paired_fastq_upload_is_accepted_and_both_mates_stored(
    client: AsyncClient, seeded_patient, monkeypatch
):
    captured = _mock_storage_and_queue(monkeypatch)

    resp = await client.post(
        "/api/submit/",
        headers={"Authorization": "Bearer test-token"},
        files={
            "biopsy_file": ("biopsy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"),
            "dna_file": ("s_R1.fastq.gz", io.BytesIO(b"@r1\nAC\n+\nII\n"), "application/gzip"),
            "dna_file_r2": ("s_R2.fastq.gz", io.BytesIO(b"@r2\nGT\n+\nII\n"), "application/gzip"),
        },
        data={"cancer_type": "Lung adenocarcinoma"},
    )

    assert resp.status_code == 202
    assert captured["uploads"] == ["biopsy.pdf", "s_R1.fastq.gz", "s_R2.fastq.gz"]


async def test_the_mate_reaches_the_worker(
    client: AsyncClient, seeded_patient, monkeypatch
):
    """Storing it and never passing it on would look identical from outside."""
    captured = _mock_storage_and_queue(monkeypatch)

    await client.post(
        "/api/submit/",
        headers={"Authorization": "Bearer test-token"},
        files={
            "biopsy_file": ("biopsy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"),
            "dna_file": ("s_R1.fastq.gz", io.BytesIO(b"@r1\nAC\n+\nII\n"), "application/gzip"),
            "dna_file_r2": ("s_R2.fastq.gz", io.BytesIO(b"@r2\nGT\n+\nII\n"), "application/gzip"),
        },
        data={"cancer_type": "Lung adenocarcinoma"},
    )

    assert captured["job_args"] is not None
    assert captured["job_args"][-1] is not None, "mate 2 key was not passed to the worker"


async def test_single_end_submission_still_works_and_passes_no_mate(
    client: AsyncClient, seeded_patient, monkeypatch
):
    captured = _mock_storage_and_queue(monkeypatch)

    resp = await client.post(
        "/api/submit/",
        headers={"Authorization": "Bearer test-token"},
        files={
            "biopsy_file": ("biopsy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"),
            "dna_file": ("sample.vcf", io.BytesIO(b"##VCF"), "text/plain"),
        },
        data={"cancer_type": "Melanoma"},
    )

    assert resp.status_code == 202
    assert captured["job_args"][-1] is None


async def test_a_mate_alongside_a_vcf_is_rejected(
    client: AsyncClient, seeded_patient, monkeypatch
):
    """
    Accepting it and ignoring it is the failure this whole entry is about: the
    caller would see 202 and believe both files were used.
    """
    _mock_storage_and_queue(monkeypatch)

    resp = await client.post(
        "/api/submit/",
        headers={"Authorization": "Bearer test-token"},
        files={
            "biopsy_file": ("biopsy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"),
            "dna_file": ("sample.vcf", io.BytesIO(b"##VCF"), "text/plain"),
            "dna_file_r2": ("s_R2.fastq.gz", io.BytesIO(b"@r2\nGT\n+\nII\n"), "application/gzip"),
        },
        data={"cancer_type": "Melanoma"},
    )

    assert resp.status_code == 422


# ── The worker passes it to Nextflow ─────────────────────────────────────────

def test_worker_forwards_the_mate_as_reads_r2(monkeypatch, tmp_path):
    import subprocess

    from workers import genomic_worker

    captured: dict = {}

    class _Result:
        returncode = 0
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out = tmp_path / "results"
        out.mkdir(exist_ok=True)
        (out / "x.annotated.vcf").write_text("##fileformat=VCFv4.2\n")
        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr("config.settings.environment", "production", raising=False)

    genomic_worker._run_nextflow_pipeline(
        str(tmp_path / "s_R1.fastq.gz"),
        str(tmp_path),
        "Lung adenocarcinoma",
        reads_r2=str(tmp_path / "s_R2.fastq.gz"),
    )

    assert "--reads_r2" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--reads_r2") + 1].endswith("s_R2.fastq.gz")


def test_worker_omits_reads_r2_when_there_is_no_mate(monkeypatch, tmp_path):
    import subprocess

    from workers import genomic_worker

    captured: dict = {}

    class _Result:
        returncode = 0
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out = tmp_path / "results"
        out.mkdir(exist_ok=True)
        (out / "x.annotated.vcf").write_text("##fileformat=VCFv4.2\n")
        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr("config.settings.environment", "production", raising=False)

    genomic_worker._run_nextflow_pipeline(
        str(tmp_path / "s.fastq.gz"), str(tmp_path), "Melanoma"
    )

    assert "--reads_r2" not in captured["cmd"]


def test_task_signature_tolerates_a_redelivered_five_argument_message():
    """
    Tasks are acks_late, so a message enqueued before this change can be
    redelivered to a worker running after it. The mate parameter defaults, so
    that message runs single-end instead of raising.
    """
    import inspect

    from workers.genomic_worker import run_genomic_pipeline

    sig = inspect.signature(run_genomic_pipeline)
    assert sig.parameters["dna_r2_s3_key"].default is None

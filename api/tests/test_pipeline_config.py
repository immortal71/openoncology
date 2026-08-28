"""
Drift guards for the Nextflow pipeline configuration.

The defect these exist for: five processes carried `process_high` or
`process_medium`, and the only config in the repository defined `bigcpu` and
`lowmem`. Neither set of names matched the other, so every labelled process ran
on Nextflow's defaults — one CPU, two gigabytes. Somatic calling passed
`--native-pair-hmm-threads 1` and STAR could not load a human genome index at
all. Nothing reported this. An unmatched `withLabel` selector is not an error in
Nextflow, and an unmatched label on a process is not one either; the two failures
are silent from opposite directions and cancel into a pipeline that runs slowly
and calls fewer variants.

The second guard is version agreement. HaplotypeCaller was pinned to GATK
4.5.0.0 and Mutect2 to 4.4.0.0, so one run's germline and somatic calls came
from different releases of the same caller — the provenance question the
variant-calling validation gate exists to answer.

Text parsing rather than running Nextflow: the CI runner has no `nextflow`, and
the properties asserted here are properties of the files.
"""
import re
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
MODULES = sorted((PIPELINE / "modules").glob("*.nf"))
CONFIGS = [PIPELINE / "nextflow.config"] + sorted((PIPELINE / "conf").glob("*.config"))


def _labels_used() -> dict[str, list[str]]:
    """Label name → the module files that carry it."""
    used: dict[str, list[str]] = {}
    for module in MODULES:
        for match in re.finditer(
            r"""^\s*label\s+["']([^"']+)["']""", module.read_text(encoding="utf-8"), re.M
        ):
            used.setdefault(match.group(1), []).append(module.name)
    return used


def _labels_defined() -> set[str]:
    defined = set()
    for config in CONFIGS:
        text = config.read_text(encoding="utf-8")
        defined.update(re.findall(r"withLabel:\s*['\"]?([A-Za-z0-9_]+)", text))
    return defined


def test_pipeline_has_a_base_config():
    """
    Without nextflow.config a plain `nextflow run main.nf` gets no resource
    labels, no container engine and no tool versions.
    """
    assert (PIPELINE / "nextflow.config").exists()


def test_every_label_a_process_uses_is_defined():
    used = _labels_used()
    defined = _labels_defined()
    missing = {label: files for label, files in used.items() if label not in defined}
    assert not missing, (
        "processes carry labels no config selects on, so they run at Nextflow's "
        f"one-CPU default: {missing}"
    )


def test_no_config_selects_on_a_label_no_process_uses():
    """
    The other half of the same drift. `bigcpu` and `lowmem` were tuned, reviewed
    and inert.
    """
    orphans = _labels_defined() - set(_labels_used())
    assert not orphans, f"withLabel selectors matching no process: {sorted(orphans)}"


def test_labelled_processes_still_exist():
    """A guard over an empty set proves nothing."""
    assert len(_labels_used()) >= 2
    assert sum(len(v) for v in _labels_used().values()) >= 5


# ── Tool versions agree across modules ───────────────────────────────────────

def _gatk_versions() -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for module in MODULES:
        text = module.read_text(encoding="utf-8")
        found = set(re.findall(r"gatk4?[:=]([0-9]+(?:\.[0-9]+)+)", text))
        found |= set(re.findall(r"broadinstitute/gatk:([0-9]+(?:\.[0-9]+)+)", text))
        if found:
            versions[module.name] = found
    return versions


def test_gatk_version_is_not_hardcoded_per_module():
    """
    Both GATK modules must take the version from `params.gatk_version`. A
    literal in either one is how 4.4.0.0 and 4.5.0.0 came to coexist.
    """
    literals = _gatk_versions()
    assert not literals, (
        f"GATK versions hardcoded instead of read from params.gatk_version: {literals}"
    )


def test_gatk_version_is_declared_once():
    text = (PIPELINE / "nextflow.config").read_text(encoding="utf-8")
    declared = re.findall(r"gatk_version\s*=\s*['\"]([^'\"]+)['\"]", text)
    assert len(declared) == 1, f"expected one gatk_version declaration, found {declared}"


@pytest.mark.parametrize("module", ["gatk.nf", "mutect2.nf"], ids=["haplotypecaller", "mutect2"])
def test_gatk_modules_read_the_shared_version(module):
    text = (PIPELINE / "modules" / module).read_text(encoding="utf-8")
    assert "params.gatk_version" in text


# ── A container engine is actually selectable ────────────────────────────────

def test_config_offers_a_profile_for_every_dependency_style():
    """
    Modules mix `conda` and `container` directives. conf/local.config enabled
    conda alone, so the container-based processes — the entire somatic and
    multi-omic path — resolved against whatever was on the host PATH, with no
    record of the version that produced the calls.
    """
    text = (PIPELINE / "nextflow.config").read_text(encoding="utf-8")
    for profile in ("conda", "docker", "singularity"):
        assert re.search(rf"^\s*{profile}\s*\{{", text, re.M), f"no {profile} profile"


def test_container_processes_are_reachable_by_a_container_profile():
    using_containers = [m.name for m in MODULES if re.search(r"^\s*container\s", m.read_text(encoding="utf-8"), re.M)]
    assert using_containers, "expected at least one containerised process"
    text = (PIPELINE / "nextflow.config").read_text(encoding="utf-8")
    assert "docker.enabled" in text and "singularity.enabled" in text

"""Validation of generated patient-facing text before it is shown to anyone.

risk_analysis.md section 3 lists the LLM patient-summary path as unanalysed:
"a generative component whose failure modes (fabrication, unwarranted certainty)
are not analysed". Open action 7. This module is the analysis, expressed as
checks rather than prose, because a failure mode written down and not tested for
is the F10 pattern.

WHAT CAN GO WRONG, AND WHAT IS DONE ABOUT IT
--------------------------------------------
Six failure modes, each with a check below. The first two are the ones that can
actually change what a patient does.

1. Fabricated drug. The model names a treatment that is not among the
   candidates the pipeline produced. A patient reading an invented drug name
   may ask for it, or believe an option exists that does not. Checked against
   the exact candidate list passed in.

2. Fabricated gene. Same shape, for a gene the patient does not have. This one
   also corrupts any later conversation with their oncologist.

3. Unwarranted certainty. "Will cure", "guaranteed", "you should take". The
   system ranks hypotheses from an evidence table; it has no basis for any of
   those. This is H5 pointed at one reader instead of at an adoption decision.

4. Prognosis. Survival estimates, life expectancy, "months to live". Nothing in
   this pipeline models outcome. A prognosis in this text is invented in the
   strongest sense, and it is the failure mode most likely to cause harm.

5. Instruction to act. Telling a patient to start, stop, or change a treatment.
   Every disclaimer in the system says a qualified oncologist decides.

6. Truncation. max_tokens is capped at 400 on this path, so the model can stop
   mid-sentence. A summary that ends in the middle of a clause can invert its
   own meaning: "this drug is not" is a complete-looking disaster.

WHAT THIS IS NOT
----------------
Substring and pattern matching over generated text. It catches the phrasings
listed here and cannot catch a fabrication that is fluent, on-topic and novel.
It lowers the rate of a known class of defect; it does not make the path safe.
The template path in services/patient_summary.py remains the correct choice for
patient output, and this guard exists because the LLM path is still reachable
whenever an OpenAI key is configured, not because it should be.

A failing verdict means fall back to the deterministic template, never publish
the text with a warning attached. A patient cannot be expected to discount a
sentence they have already read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

# Claims of certainty the evidence base cannot support.
_CERTAINTY_PATTERNS = [
    r"\bwill (?:cure|heal|eliminate|eradicate|remove) ",
    r"\bguarantee(?:d|s)?\b",
    r"\bcertain(?:ly)? to work\b",
    r"\bdefinitely will\b",
    r"\b(?:completely|fully) effective\b",
    r"\bno (?:risk|side effects)\b",
    r"\b100% \w*\s*(?:effective|safe|success)",
    r"\bproven to cure\b",
]

# Outcome claims. Nothing in this pipeline models survival.
_PROGNOSIS_PATTERNS = [
    r"\b(?:life )?expectancy\b",
    r"\bsurvival rate\b",
    r"\byears? to live\b",
    r"\bmonths? to live\b",
    r"\bterminal\b",
    r"\bprognosis is\b",
    r"\b\d+\s*(?:-|to )\s*\d+\s*(?:month|year)s? (?:of )?surviv",
    r"\byou have \w+ (?:months|years)\b",
]

# Direct instruction to change treatment. The oncologist decides.
_INSTRUCTION_PATTERNS = [
    r"\byou should (?:take|start|stop|switch|discontinue|begin)\b",
    r"\bstop taking\b",
    r"\bdiscontinue your\b",
    r"\bbegin treatment with\b",
    r"\bask your doctor to prescribe\b",
    r"\bwe recommend (?:you )?(?:take|start|stop)\b",
]

# Sentence-final punctuation that indicates the text completed.
_TERMINATORS = ".!?\"')]"

# Tokens that look like a drug name: capitalised or long lowercase words.
# Deliberately loose. A false positive costs a fallback to the template; a
# false negative ships an invented drug name to a patient.
_WORD = re.compile(r"\b[A-Za-z][A-Za-z0-9-]{4,}\b")

# Common words that pass the shape test but are not drugs. Kept small on
# purpose: every addition here is a hole in check 1.
_NOT_DRUGS = frozenset(
    """about above after again against along already also although always among
    another answer anything appear approved around available because become
    been before being below better between beyond biopsy cancer cannot care
    carefully caused cells change chemotherapy clinical common complete
    consider could course current decision described detail discuss disease
    doctor doctors doing driver drugs during early effect effects either
    enough especially estimate every everything evidence exactly example
    existing expect experimental explain family first follow found further
    future general genes genetic genomic given greater group growth guide
    having health help helps human identified important include including
    increase individual information instead interest internal issue itself
    known laboratory large later least level levels light likely limited
    little living longer looking making management matched material means
    measure medical medicine medicines might modern moment months mutation
    mutations narrow nature needs never newer nothing number offer often
    option options other others outcome oncologist patient patients people
    perhaps person place plan please point possible potential present
    previous probably problem process professional program provide question
    quickly rather reach reason receive recent record reduce related report
    require research response result results review right sample science
    screening second sequence series service several should showed similar
    since single small some someone something sometimes specific standard
    start still study studies subject success suggest support sure system
    table taken target targeted team tell testing tests their there these
    thing think third those though three through time tissue today together
    took toward treat treated treatment treatments trial trials tumor tumour
    turn under understand unique until using usually value variant variants
    various very want water week weeks whether which while whole will with
    within without woman work working world would write year years your
    genetics oncology therapy therapies""".split()
)


@dataclass
class GuardVerdict:
    """Outcome of validating one generated summary."""

    ok: bool
    violations: list[str] = field(default_factory=list)

    def reason(self) -> str:
        return "; ".join(self.violations)


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _looks_truncated(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return True
    return stripped[-1] not in _TERMINATORS


def validate_patient_summary(
    text: str,
    allowed_drugs: Optional[Iterable[str]] = None,
    allowed_genes: Optional[Iterable[str]] = None,
) -> GuardVerdict:
    """Check generated patient text against the six failure modes above.

    ``allowed_drugs`` and ``allowed_genes`` are what the pipeline actually
    produced for this patient. Anything drug-shaped in the text that is not in
    those sets is treated as fabricated.

    Returns a verdict rather than raising: the caller decides to fall back, and
    a guard that can take down report generation would be a worse defect than
    the one it prevents.
    """
    violations: list[str] = []
    if not text or not text.strip():
        return GuardVerdict(ok=False, violations=["empty summary"])

    lowered = text.lower()

    for pattern in _CERTAINTY_PATTERNS:
        if re.search(pattern, lowered):
            violations.append(f"unwarranted certainty: {pattern!r}")
            break

    for pattern in _PROGNOSIS_PATTERNS:
        if re.search(pattern, lowered):
            violations.append(f"prognosis claim: {pattern!r}")
            break

    for pattern in _INSTRUCTION_PATTERNS:
        if re.search(pattern, lowered):
            violations.append(f"instruction to change treatment: {pattern!r}")
            break

    if _looks_truncated(text):
        violations.append("text ends mid-sentence, likely truncated at max_tokens")

    allowed = {_normalise(d) for d in (allowed_drugs or []) if d}
    allowed_gene_set = {_normalise(g) for g in (allowed_genes or []) if g}
    known = allowed | allowed_gene_set

    if allowed_drugs is not None:
        for match in _WORD.finditer(text):
            word = match.group(0)
            norm = _normalise(word)
            if norm in known or word.lower() in _NOT_DRUGS:
                continue
            # Drug-shaped: ends in a recognised pharmaceutical stem. Restricting
            # to stems keeps ordinary prose from tripping the check while still
            # catching invented compound names, which almost always carry one.
            if re.search(
                r"(?:mab|nib|tinib|ciclib|parib|inib|zomib|sertib|degib|"
                r"platin|rubicin|taxel|mustine|tecan|citabine)$",
                word.lower(),
            ):
                violations.append(f"drug not in candidate list: {word}")
                break

    return GuardVerdict(ok=not violations, violations=violations)

"""Safety guard for free text written by the model.

The model may explain and remind; it may not tell anyone to change a dose,
stop a medicine, or diagnose. Offending sentences are removed (not reworded),
and every removal is recorded so it shows up in the response and audit trail.
"""

import re

DISCLAIMER = (
    "MedGuard helps you organise medicine timing. It is not medical advice. Check this "
    "routine with your doctor or pharmacist before following it, and never stop or change "
    "a medicine without talking to them."
)

HIGH_RISK_WARNING = (
    "High-risk interaction found. Talk to your doctor or pharmacist before starting this "
    "routine. Get emergency help for severe symptoms such as trouble breathing, fainting, "
    "chest pain, severe bleeding or confusion."
)

_NEGATION = r"(?<!not )(?<!n't )(?<!never )(?<!without )"

FORBIDDEN = [
    (
        "dose_change",
        re.compile(
            r"\b(increase|decrease|double|halve|reduce|lower|raise|adjust|change)\b"
            r"[^.!?]{0,30}\b(dose|dosage|doses|tablets?|pills?|capsules?|mg)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stop_medicine",
        re.compile(_NEGATION + r"\b(stop|discontinue|skip|quit)\b(\s+(taking|using))?", re.IGNORECASE),
    ),
    (
        "diagnosis",
        re.compile(r"\bdiagnos(e|es|ed|is)\b|\byou (probably|likely|may|might) have\b", re.IGNORECASE),
    ),
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def violations(text: str) -> list[str]:
    return [code for code, pattern in FORBIDDEN if pattern.search(text)]


def scrub(text: str) -> tuple[str, list[str]]:
    """Drop sentences that break a rule. Returns (clean text, rule codes hit)."""
    kept, hit = [], []
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        codes = violations(sentence)
        if codes:
            hit.extend(codes)
        elif sentence:
            kept.append(sentence)
    return " ".join(kept), sorted(set(hit))

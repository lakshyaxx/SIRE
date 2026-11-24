"""Conservative review flags for visibly unfinished mechanism descriptions."""

import re
import json
import unicodedata
from app.core.config import SETTINGS
from app.investigation.schemas import EvidenceItem, Proposal


def _normalized(value: str) -> str:
    return " ".join(re.sub(r"[-_]", " ", value.casefold()).split())


def issues(text: str) -> list[str]:
    """Flag obvious textual fragments without treating fluent prose as a verified mechanism."""
    result = []
    if not text.strip():
        result.append("Mechanism text is empty; no complete explanation was produced.")
    if re.search(r"[,;:—-]\s*$", text):
        result.append(
            "Mechanism ends with continuation punctuation; explanation may be incomplete."
        )
    prose = re.sub(r"\[[^\]]+\]", "", text).strip()
    if re.search(
        r"\b(?:because|due to|caused by|resulting in|leading to|and|or|with|of|from|the|a|an|to|not|is|are|was|were|has|have|may|might|could|would|should|will|in|by|at|for|as|than|if|when|while)\s*[.,;:!?]*$",
        prose,
        re.I,
    ):
        result.append(
            "Mechanism ends with an unfinished clause; human review is required."
        )
    if any(
        text.count(left) != text.count(right)
        for left, right in [("(", ")"), ("[", "]")]
    ):
        result.append(
            "Mechanism contains unmatched delimiters; human review is required."
        )
    unexpected_scripts = sorted(
        {
            unicodedata.name(character, "UNKNOWN").split()[0]
            for character in text
            if character.isalpha() and "LATIN" not in unicodedata.name(character, "")
        }
    )
    if unexpected_scripts:
        result.append(
            "Mechanism contains unexpected language-script drift "
            f"({', '.join(unexpected_scripts)}); output was withheld."
        )
    return result


def evidence_issues(
    text: str, evidence: list[EvidenceItem], *, assertion: bool = True
) -> list[str]:
    """Reject narrow, source-contradicted report claims and unqualified cross-domain chains."""
    generated = _normalized(text)
    found = []
    if assertion:
        found.extend(observation_role_issues(text, evidence))
    for item in evidence:
        source = _normalized(item.observation)
        if item.kind == "measurement":
            try:
                measurement = json.loads(item.observation)
            except (ValueError, TypeError):
                measurement = {}
            channel = (
                measurement.get("channel", "") if isinstance(measurement, dict) else ""
            )
            aliases = [
                channel.replace("_", " "),
                *SETTINGS.get("measurement_channel_aliases", {}).get(channel, []),
            ]
            for alias in filter(None, aliases):
                if measurement.get("delta") and re.search(
                    r"\b"
                    + re.escape(alias)
                    + r"\b[^.;]{0,35}\b(?:remains?|stays?|is|was)\s+(?:stable|constant)\b",
                    generated,
                ):
                    found.append(
                        "Channel stability was asserted despite a nonzero source window change and no supplied stability criterion; report the measured change or qualify the claim."
                    )
        absent = re.findall(
            r"\bno\s+([a-z ]{1,60}?\breport)\s+(?:is\s+)?(?:available|provided)", source
        )
        absent += re.findall(
            r"\b((?:[a-z]+\s+){0,3}report)\s+(?:is\s+)?(?:not available|unavailable|not provided)",
            source,
        )
        for subject in absent:
            words = set(subject.split()) - {"the", "a", "this", "no", "is", "report"}
            if (
                not words
                or not words <= set(generated.split())
                or "report" not in generated
            ):
                continue
            for match in re.finditer(
                r"\b(?:available|completed|obtained|received|existing|exists|dated)\b",
                generated,
            ):
                prefix = generated[max(0, match.start() - 80) : match.start()]
                negative = re.search(
                    r"\bnot\s+(?:currently\s+)?$", prefix
                ) or re.search(r"\bno\s+[^.;]{0,65}\breport\s+(?:is\s+)?$", prefix)
                question = re.search(r"\b(?:whether|if|confirm|verify|check)\b", prefix)
                if not negative and not question:
                    found.append(
                        "Report availability or completion was asserted despite a source saying the report was unavailable; a maintenance check is not an analytical test."
                    )
                    break
            if re.search(
                r"\breport\s+from\b.*\b(?:check|maintenance|days?|ago)\b", generated
            ) and not re.search(r"\b(?:whether|if|new|obtain|perform)\b", generated):
                found.append(
                    "A report was attributed to a past maintenance event despite its existence being unestablished; request a new analysis or confirmation instead."
                )
    for sentence in re.split(r"[.!?;]+", generated) if assertion else []:
        if (
            re.search(r"\b(?:bearing|misalignment|lubrication|lubricant)\b", generated)
            and re.search(r"\b(?:flow|airflow|pressure)\b", sentence)
            and re.search(
                r"\b(?:causes?|causing|leads?|leading|results?|resulting|reduces?|reduced)\b",
                sentence,
            )
            and not re.search(
                r"\b(?:may|might|could|possible|unconfirmed|not established|unexplained|hypothetical)\b",
                sentence,
            )
        ):
            found.append(
                "An unqualified mechanical-to-hydraulic causal chain is not established by correlated observations; scope the mechanism or state the missing linkage."
            )
    if re.search(r"\b(?:not the|exclude[ds]?|ruled out)\b", generated) and re.search(
        r"\b(?:given|because|since|due to)\b.*\b(?:no|missing|unavailable)\b.*\breport\b",
        generated,
    ):
        found.append(
            "An unavailable analytical report cannot exclude a cause; absence of a test is not a negative test result."
        )
    return list(dict.fromkeys(found))


def observation_role_issues(text: str, evidence: list[EvidenceItem]) -> list[str]:
    """Flag assertions that turn an explicitly unmeasured or commanded state into an observation."""
    unknown = []
    for item in evidence:
        for clause in re.split(r"[.;\n]+", _normalized(item.observation)):
            match = re.search(
                r"(?:^|\b)([a-z ]{2,65}?)\s+(?:(?:has|have|is|are|was|were)\s+)?(?:(?:not|never)\s+(?:been\s+)?(?:measured|verified|tested|observed)|(?:is\s+)?(?:unknown|unavailable|unverified))\b",
                clause,
            )
            if match:
                words = [
                    word
                    for word in match[1].split()
                    if word
                    not in {
                        "the",
                        "a",
                        "an",
                        "actual",
                        "physical",
                        "direct",
                        "operation",
                        "status",
                        "measurement",
                        "measurements",
                        "reading",
                        "readings",
                    }
                ]
                if words:
                    unknown.append(words[-2:])
            command = re.search(
                r"\b([a-z]+)\s+(?:was\s+|is\s+)?commanded\s+(?:on|off|open|closed|running|stopped)\b",
                clause,
            )
            if command:
                unknown.append([command[1]])
    reasons = []
    for clause in re.split(r"[.;\n]+", _normalized(text)):
        conditional = re.search(
            r"\b(?:may|might|could|can|would|possible|possibly|potential|hypothetical|unconfirmed|conditional|if|whether|unknown|unverified|unmeasured|missing|unavailable|required|needed|not established|not confirmed|not measured|not verified|needs? verification|(?:was|is) commanded)\b|\bno\b[^.;]{0,70}\b(?:measured|verified|tested|measurements?|readings?)\b",
            clause,
        )
        if not conditional:
            for topic in unknown:
                if all(
                    re.search(r"\b" + re.escape(word) + r"\b", clause) for word in topic
                ) and re.search(
                    r"\b(?:is|are|was|were|has|have|observed|confirmed|measured|verified|dropped|decreased|increased|fell|low|high|running|operating)\b",
                    clause,
                ):
                    reasons.append(
                        "A state explicitly unmeasured, unverified or commanded in the supplied reports was promoted to an observation; keep it unknown or conditional."
                    )
                    break
        if (
            re.search(
                r"\b(?:missing|unavailable|unmeasured|not measured|not provided|no measurements?)\b",
                clause,
            )
            and re.search(
                r"\b(?:proves?|confirms?|demonstrates?|establishes?|supports?)\b",
                clause,
            )
            and not re.search(
                r"\b(?:does not|cannot|can't|not evidence|doesn't)\b|\b(?:to|would|could|may|might)\s+(?:prove|confirm|demonstrate|establish|support)\b",
                clause,
            )
        ):
            reasons.append(
                "Missing evidence cannot be positive support or confirmation of a fault."
            )
        for certainty in re.finditer(
            r"\b(?:confirmed|proven|definite|necessarily|always causes?)\b", clause
        ):
            prefix = clause[max(0, certainty.start() - 45) : certainty.start()]
            if not conditional and not re.search(
                r"\b(?:no|not|never|without|cannot)\b", prefix
            ):
                reasons.append(
                    "A definitive physical conclusion was asserted without independent confirmation criteria; retain a tentative mechanism and discriminating test."
                )
    return list(dict.fromkeys(reasons))


def review(proposal: Proposal, evidence: list[EvidenceItem]) -> dict[str, list[str]]:
    """Check generated fields without rewriting their content or inventing completion."""
    result = {}
    for candidate in proposal.hypotheses:
        reasons = issues(candidate.mechanism) + evidence_issues(
            candidate.mechanism, evidence
        )
        for text in [*candidate.assumptions, *candidate.missing_tests]:
            reasons.extend(issues(text))
            reasons.extend(evidence_issues(text, evidence, assertion=False))
        for sign in candidate.expected_signs:
            reasons.extend(issues(sign.predicate))
        if reasons:
            result[candidate.id] = list(dict.fromkeys(reasons))
    unresolved = [
        reason
        for text in proposal.unresolved
        for reason in issues(text) + evidence_issues(text, evidence)
    ]
    if unresolved:
        result["unresolved"] = list(dict.fromkeys(unresolved))
    return result

"""Conservative review flags for visibly unfinished mechanism descriptions."""

import re


def issues(text: str) -> list[str]:
    """Flag obvious textual fragments without treating fluent prose as a verified mechanism."""
    result = []
    if re.search(
        r"\b(?:because|due to|caused by|resulting in|leading to|and|or|with|of|from|the|a|an|to)\s*[.,;:!?]*$",
        text,
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
    return result

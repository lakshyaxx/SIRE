"""Transparent English text normalization for a local lexicon-only speech front end."""

from pathlib import Path
from functools import lru_cache
import re
from app.core.errors import SireError

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()


@lru_cache(maxsize=1)
def _lexicon_words(content: bytes) -> frozenset[str]:
    """Reuse one exact parsed lexicon snapshot; never cache user text or file metadata."""
    return frozenset(
        line.split()[0].casefold()
        for line in content.decode("utf-8").splitlines()
        if line.split()
    )


def number_words(value: str) -> str:
    """Spell integers/decimals without dropping digits or inventing rounded values."""
    if value.startswith("-"):
        return "minus " + number_words(value[1:])
    if "." in value:
        integer, decimals = value.split(".", 1)
        return (
            number_words(integer)
            + " point "
            + " ".join(ONES[int(digit)] for digit in decimals)
        )
    number = int(value)
    if number < 20:
        return ONES[number]
    if number < 100:
        return TENS[number // 10] + (" " + ONES[number % 10] if number % 10 else "")
    if number < 1000:
        return (
            ONES[number // 100]
            + " hundred"
            + (" " + number_words(str(number % 100)) if number % 100 else "")
        )
    if number < 1000000:
        return (
            number_words(str(number // 1000))
            + " thousand"
            + (" " + number_words(str(number % 1000)) if number % 1000 else "")
        )
    return " ".join(ONES[int(digit)] for digit in value)


def display_safe_text(text: str) -> str:
    """Exclude code, URLs and citation identifiers from locally spoken display text."""
    text = re.sub(r"```[\s\S]*?```|~~~[\s\S]*?~~~", " ", text)
    text = re.sub(
        r"\[(?:EV:|SRC:|HYP:)[^\]]+\]|\[(?:[a-fA-F0-9]{24}|[a-fA-F0-9]{32}(?::(?:transcript|schema|visual:\d+))?|(?:prediction|user):[a-fA-F0-9]{32}|E\d+)\]",
        " ",
        text,
    )
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^[\s#>*|_-]+", " ", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def spoken_text(text: str, lexicon: Path) -> tuple[str, list[str]]:
    """Strip citation markup, expand exact numbers and explicitly spell unknown words."""
    if not text.strip() or len(text) > 1200:
        raise SireError(
            "tts_text_limit", "Choose non-empty text of at most 1200 characters."
        )
    text = display_safe_text(text)
    if any(character.isalpha() and not character.isascii() for character in text):
        raise SireError(
            "tts_unsupported_language",
            "The configured voice supports English; non-English words would be dropped, so synthesis was refused.",
            422,
        )
    known = _lexicon_words(lexicon.read_bytes())
    text = re.sub(r"\[(?:EV:|SRC:|HYP:)[^\]]+\]", "", text)
    text = re.sub(
        r"\[(?:[a-fA-F0-9]{24}|[a-fA-F0-9]{32}(?::(?:transcript|schema|visual:\d+))?|(?:prediction|user):[a-fA-F0-9]{32}|E\d+)\]",
        "",
        text,
    )
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\b(?:EV|SRC|HYP):[a-f0-9]{16,}\b", "", text)
    text = text.replace("°C", " degrees Celsius ").replace("°F", " degrees Fahrenheit ")
    text = text.replace("%", " percent ").replace("°", " degrees ")
    text = re.sub(r"-?\d+(?:\.\d+)?", lambda match: number_words(match.group()), text)
    warnings = []
    output = []
    for token in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|[.!?,;:]", text):
        if token.casefold() in known or not token[0].isalpha():
            output.append(token)
        else:
            letters = [letter.casefold() for letter in token if letter.isalpha()]
            if not all(letter in known for letter in letters):
                raise SireError(
                    "tts_unsupported_word",
                    "The local lexicon cannot pronounce this text without dropping words; use text display.",
                    422,
                )
            output.extend(letters)
            warnings.append("Spelled out-of-vocabulary word: " + token)
    if not output:
        raise SireError(
            "tts_unsupported_language",
            "The configured local voice supports English text.",
            422,
        )
    return " ".join(output), warnings

"""Evidence matching: is a gold quote present in a piece of text?

Used by `eval/verify_candidates.py` (is the quote on the cited page?) and, later, by the
retrieval eval (does a retrieved chunk contain the quote?). One `normalize` for both, so the
two checks cannot disagree.
"""

import re
import unicodedata

# Markdown that the parser adds and that a quote copied from the PDF does not have.
_MARKDOWN = re.compile(r"[|#*_`>]")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, drop markdown symbols, collapse whitespace.

    Table pipes become spaces, so "|2,600 ton/day|82%|" matches the quote "2,600 ton/day 82%".
    NFKC folds ligatures and non-breaking spaces, which differ between the PDF and our text.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _MARKDOWN.sub(" ", text.lower())
    return _SPACE.sub(" ", text).strip()


def contains_quote(text: str, quote: str) -> bool:
    """True if the normalized quote is a substring of the normalized text."""
    q = normalize(quote)
    return bool(q) and q in normalize(text)


def n_words(quote: str) -> int:
    return len(quote.split())


_STOPWORDS = frozenset(
    ["the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is", "are", "was", "were", "what", "which", "who", "whom", "how", "does", "do", "did", "by", "with", "from", "as", "at", "be", "that", "this", "it", "its", "their", "than", "between", "under", "over", "per", "into", "during"]
)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9,.\-]*[a-z0-9]|[a-z0-9]")


def content_tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(normalize(text)) if t not in _STOPWORDS}


def question_overlap(question: str, quotes: list[str]) -> float:
    """Share of the question's content words that also occur in the evidence quotes.

    A difficulty proxy that needs no retrieval run: near 0 means the question is worded
    differently from its evidence (a vocabulary mismatch); near 1 means it can be answered by
    matching words. It is a property of the question, so it is safe to report by group.
    """
    q = content_tokens(question)
    if not q:
        return 0.0
    evidence = set().union(*(content_tokens(x) for x in quotes)) if quotes else set()
    return len(q & evidence) / len(q)


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def numbers_in(text: str) -> set[str]:
    """Numbers in a text, written the same way everywhere: "2,137" -> "2137", "0.043" stays.

    Thousands commas are dropped so a quote's "7,366" matches an answer's "7366"; a decimal
    point is kept ("0.043" is not "0043"). Currency, units and percent signs are ignored.
    """
    found = set()
    for raw in _NUMBER.findall(normalize(text)):
        # "1,5" with a comma and no thousands shape is rare in these English documents.
        found.add(raw.replace(",", "").rstrip("."))
    return found


def unsupported_numbers(answer: str, question: str, quotes: list[str]) -> list[str]:
    """Numbers that the reference answer states but neither the question nor any quote contains.

    A heuristic for review, not a verdict (single digits are ignored): such a number may be a calculation (a difference, a
    percentage) or a figure the generator invented. Sorted so the output is stable.
    """
    allowed = numbers_in(question).union(*(numbers_in(q) for q in quotes))
    # Single digits are mostly list markers ("(1) ... (2) ..."), which flooded the first version.
    # The cost: a wrong single-digit figure is not caught here.
    return sorted(n for n in numbers_in(answer) - allowed if len(n) > 1)

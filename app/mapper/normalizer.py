"""Normalization utilities for service name matching (AWS and non-AWS)."""

import re
from typing import List


# Generic words that appear in descriptive labels but are not AWS service
# names. Individual tokens matching these are skipped to avoid accidental
# matches against unrelated classes in the diagrams.aws hierarchy.
_STOPWORDS = {
    "aws", "amazon", "the", "by", "for", "and", "or", "to", "of", "in",
    "on", "with", "a", "an", "managed", "state", "lock", "plan",
    "apply", "source", "manual", "approval", "pipeline", "stopped",
    "repository", "app", "account", "environment", "artifacts", "service",
    "services", "infrastructure", "request", "notification",
    "read", "write", "init", "push", "main", "target", "devops",
}

# Matches any character that is NOT an ASCII letter or digit. Used to strip
# emojis, punctuation, slashes, parentheses, plus signs, and all other
# non-alphanumeric noise so that only the meaningful service name remains.
_NON_ALNUM = re.compile(r"[^a-z0-9]")

# Splits a label into candidate word tokens on any run of non-alphanumeric
# characters (whitespace, slashes, parentheses, emojis, etc.).
_TOKEN_SPLIT = re.compile(r"[^A-Za-z0-9]+")


def normalize_service_name(label: str) -> str:
    """Normalize a node label for service matching.

    Lowercases the label, removes HTML tags (like <br/>), and strips ALL
    non-alphanumeric characters (whitespace, hyphens, underscores, emojis,
    punctuation), leaving only ASCII letters and digits.

    Args:
        label: The raw node label from Mermaid syntax.

    Returns:
        Normalized string for lookup in service maps.
    """
    # Strip HTML tags like <br/>, <br>, etc.
    cleaned = re.sub(r"<[^>]+>", " ", label)
    # Lowercase, then remove every non-alphanumeric character.
    return _NON_ALNUM.sub("", cleaned.lower())


def _normalize_token(text: str) -> str:
    """Lowercase a token and strip all non-alphanumeric characters.

    Args:
        text: The raw token text.

    Returns:
        The normalized token (ASCII letters and digits only).
    """
    return _NON_ALNUM.sub("", text.lower())


def extract_service_candidates(label: str) -> List[str]:
    """Extract possible AWS service name candidates from a label.

    Generates candidates in priority order so that more specific matches
    are tried before broader ones:

      1. Each <br/>-delimited segment, normalized (with amazon/aws prefix
         stripped variants).
      2. The full label normalized.
      3. Individual word tokens split on any non-alphanumeric run (to catch
         service names embedded in descriptive labels like
         "Networking (VPC / Subnets)" -> "networking", "vpc", "subnets"),
         excluding generic stopwords and very short tokens to avoid false
         positives against the large diagrams.aws class hierarchy.

    Emojis and punctuation are removed throughout, so labels like
    "🌐 Networking" resolve the same as "Networking".

    Examples:
      - "Amazon S3<br/>Pipeline Artifacts" -> ["amazons3", "s3", ...]
      - "S3 Terraform State" -> ["s3terraformstate", "s3", ...]
      - "🌐 Networking<br/>(VPC / Subnets)" -> ["networking", "vpc", "subnets", ...]

    Args:
        label: The raw node label from Mermaid syntax.

    Returns:
        Ordered list of normalized candidate strings to try for matching.
    """
    candidates: List[str] = []

    def _add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    # Strip HTML tags for token processing
    tag_free = re.sub(r"<[^>]+>", " ", label)

    # 1. Segments split on <br/> (retain original behavior + prefix stripping)
    parts = re.split(r"<br\s*/?>", label, flags=re.IGNORECASE)
    for part in parts:
        normalized = _normalize_token(part)
        for prefix in ("amazon", "aws"):
            if normalized.startswith(prefix) and len(normalized) > len(prefix):
                _add(normalized[len(prefix):])
        _add(normalized)

    # 2. Full label normalized
    _add(normalize_service_name(label))

    # 3. Individual word tokens - split on any non-alphanumeric run so that
    #    emojis, slashes, and parentheses act as separators. Skip stopwords
    #    and very short tokens to prevent accidental matches.
    for word in _TOKEN_SPLIT.split(tag_free):
        token = _normalize_token(word)
        if len(token) < 2:
            continue
        if token in _STOPWORDS:
            continue
        for prefix in ("amazon", "aws"):
            if token.startswith(prefix) and len(token) > len(prefix):
                _add(token[len(prefix):])
        _add(token)

    return candidates

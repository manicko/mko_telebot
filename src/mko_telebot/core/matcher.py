"""Pattern matching functionality for search queries.

This module contains functions for converting AST nodes to regex patterns
and evaluating whether text matches query patterns.
"""

import re
import logging

from .ast_nodes import ASTNode, ExactMatch, OrOperation, Sequence, Wildcard, Exclusion

logger = logging.getLogger(__name__)


def ast_to_regex(node: ASTNode) -> str:
    r"""Build a single regex string for a given AST node.

    The function converts basic AST node types to regex patterns:
      - ExactMatch -> r"\bword\b" (word boundaries used)
      - Wildcard  -> '*' is converted to '[^\s]*' (match any non-space sequence)
        Word boundaries are added unless '*' sits at the term start/end.
      - OrOperation -> non-capturing group combining left|right
      - Exclusion -> delegates to child (used for building exclusion patterns)
      - Sequence is not handled here (handled by patterns_for_node)

    Args:
        node: An ASTNode instance.

    Returns:
        A regex string (possibly empty for unsupported node types).
    """
    if isinstance(node, ExactMatch):
        return rf"\b{re.escape(node.value)}\b"
    if isinstance(node, Wildcard):
        orig = node.pattern
        # Escape the pattern, then convert escaped '*' into regex matching any non-space sequence.
        escaped = re.escape(orig)
        pattern = escaped.replace(r"\*", r"[^\s]*")
        # If pattern does not start with '*', add word boundary
        if not orig.startswith("*"):
            pattern = r"\b" + pattern
        # If pattern does not end with '*', add closing word boundary
        if not orig.endswith("*"):
            pattern = pattern + r"\b"
        return pattern
    if isinstance(node, OrOperation):
        left = ast_to_regex(node.left)
        right = ast_to_regex(node.right)
        return f"(?:{left}|{right})"
    if isinstance(node, Exclusion):
        return ast_to_regex(node.child)
    # Sequence should not come here for single-regex usage
    return ""


def patterns_for_node(node: ASTNode) -> list[str]:
    """Return a list of regex patterns required by the given AST node.

    Each returned regex is considered an independent requirement that must be
    found somewhere in the target text (unordered AND semantics).

    Semantics by node type:
      - ExactMatch -> [r"\bword\b"]
      - Wildcard -> [pattern] (converted according to wildcard rules)
      - OrOperation -> [r"(?:a|b)"] (single regex; any alternative suffices)
      - Sequence -> flatten patterns from each element (all must be found, any order)
      - Exclusion -> return patterns of child (to be used for exclusion checks)

    Args:
        node: ASTNode to convert to required regex patterns.

    Returns:
        List of regex strings (possibly empty).
    """
    if isinstance(node, ExactMatch):
        return [ast_to_regex(node)]
    if isinstance(node, Wildcard):
        return [ast_to_regex(node)]
    if isinstance(node, OrOperation):
        return [ast_to_regex(node)]
    if isinstance(node, Sequence):
        parts: list[str] = []
        for elem in node.elements:
            parts.extend(patterns_for_node(elem))
        return parts
    if isinstance(node, Exclusion):
        return patterns_for_node(node.child)
    return []


def _check_patterns_match(text: str, patterns: list[str]) -> bool:
    """Check if all regex patterns match in the text.

    Args:
        text: The target text to search.
        patterns: List of regex patterns (all must match).

    Returns:
        True if all patterns match, False otherwise.
    """
    if not patterns:
        return False
    for pat in patterns:
        if not pat:
            return False
        if not re.search(pat, text, flags=re.IGNORECASE | re.UNICODE):
            return False
    return True


def evaluate_query(
    text: str, inclusions: list[ASTNode], exclusions: list[ASTNode]
) -> bool:
    """Evaluate if text matches inclusion patterns and no exclusion patterns.

    Args:
        text: The target text where patterns will be searched.
        inclusions: List of ASTNode patterns that must be present.
        exclusions: List of ASTNode patterns that must NOT be present.

    Returns:
        True if text satisfies all inclusions and no exclusions match.
    """
    # First handle exclusions: if any exclusion matches -> overall False
    for excl in exclusions:
        excl_patterns = patterns_for_node(excl)
        if _check_patterns_match(text, excl_patterns):
            return False

    # Then handle inclusions: each inclusion expression requires all its
    # sub-patterns to be present somewhere in the text (unordered).
    for inc in inclusions:
        required = patterns_for_node(inc)
        if not _check_patterns_match(text, required):
            return False

    # If there were any inclusions and they all passed -> True.
    # If no inclusions but exclusions existed (and none matched) -> True.
    return len(inclusions) > 0 or len(exclusions) > 0


def search_match(text: str, query: str) -> bool:
    r"""Evaluate whether the given text matches the query expression.

    Semantics:
      - Space separates terms and acts as logical AND (all terms must be present,
        but order of terms in a Sequence is not important).
      - '|' denotes OR between alternatives.
      - A leading '-' before an expression marks it as an exclusion; if any exclusion
        matches the text, the whole match fails.
      - Parentheses '()' allow grouping.
      - '*' inside a term is treated as a wildcard that matches any non-space sequence.
        Example: 'bike*' -> r'\bbike[^\s]*\b' (if '*' at end, right boundary omitted accordingly).

    The evaluation order is:
      1. Parse query into inclusions and exclusions.
      2. Check exclusions first: if any exclusion pattern matches -> return False.
      3. Check inclusions next: each inclusion must have all its required patterns found
         in the text (for ORs, patterns_for_node returns a single OR pattern).
      4. If there are inclusions and all passed -> True. If there were no inclusions but
         there were exclusions that did not match -> True. Otherwise -> False.

    Args:
        text: The target text where patterns will be searched.
        query: The query string (pattern expression).

    Returns:
        True if the text satisfies the query expression, False otherwise.
    """
    from .parser import parse_query

    try:
        inclusions, exclusions = parse_query(query)
        return evaluate_query(text, inclusions, exclusions)
    except Exception as e:
        # Log any parsing or runtime error with full traceback for diagnostics.
        # Using logger.exception automatically includes the stack trace,
        # which helps identify malformed query syntax or unexpected parsing errors.
        # The function still returns False to fail safely without raising.
        logger.exception(
            f"Error while evaluating search_match for query '{query}': {e}"
        )
        return False

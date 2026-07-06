import re
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ASTNode:
    """Base class for AST nodes representing parts of the search query pattern."""

    pass


@dataclass
class ExactMatch(ASTNode):
    """AST node representing an exact term match.

    Attributes:
        value: The exact term to match (string).
    """

    value: str


@dataclass
class OrOperation(ASTNode):
    """AST node representing a logical OR between two subexpressions.

    Attributes:
        left: Left subexpression (ASTNode).
        right: Right subexpression (ASTNode).
    """

    left: ASTNode
    right: ASTNode


@dataclass
class Sequence(ASTNode):
    """AST node representing a sequence (adjacent terms) which denotes logical AND.

    The elements of the sequence must all be present in the text (in any order
    for this implementation).
    Attributes:
        elements: List of ASTNode elements in the sequence.
    """

    elements: list[ASTNode]


@dataclass
class Wildcard(ASTNode):
    """AST node representing a term with wildcard(s) ('*').

    Attributes:
        pattern: The term pattern possibly containing '*' wildcard characters.
    """

    pattern: str


@dataclass
class Exclusion(ASTNode):
    """AST node representing an exclusion (negation) of a child expression.

    If the child expression matches, the whole expression is disqualified.
    Attributes:
        child: ASTNode that should not match.
    """

    child: ASTNode


class PatternParser:
    """Parser for the pattern query string that builds an AST.

    The parser supports:
      - Term tokens (plain words, possibly containing '*')
      - Grouping with parentheses: (...)
      - OR operator using '|'
      - Exclusion prefix using '-' (applies to the next expression)
      - Adjacency (space-separated terms) interpreted as logical AND (sequence)

    Grammar (informal):
      or_expr   := and_expr ( 'OR' and_expr )*
      and_expr  := term ( term )*   # adjacency = Sequence (AND)
      term      := 'TERM' | '(' or_expr ')'

    Notes:
      - The tokenizer treats whitespace as a separator and does not emit tokens for it.
      - '*' inside a term becomes a non-space wildcard when converted to regex.
    """

    def __init__(self, query: str):
        """Initialize the parser with the raw query string.

        Args:
            query: The raw query string (user-specified).
        """
        self.query = query
        self.tokens = self._tokenize()
        self.token_pos = 0

    def _tokenize(self) -> list[tuple[str, str]]:
        """Convert the input query string into a list of tokens.

        Token types:
          - GROUP_START: '('
          - GROUP_END: ')'
          - OR: '|'
          - EXCLUDE: '-'
          - TERM: contiguous non-special characters (a word, possibly with '*')

        Whitespace is treated as a separator (logical AND) but not emitted as a token.
        """
        tokens = []
        i = 0
        q = self.query
        while i < len(q):
            ch = q[i]
            if ch == "(":
                tokens.append(("GROUP_START", "("))
                i += 1
            elif ch == ")":
                tokens.append(("GROUP_END", ")"))
                i += 1
            elif ch == "|":
                tokens.append(("OR", "|"))
                i += 1
            elif ch == "-":
                tokens.append(("EXCLUDE", "-"))
                i += 1
            elif ch.isspace():
                # Space serves as a separator (AND), tokens for spaces are not needed.
                i += 1
            else:
                # TERM: read until special character or whitespace
                start = i
                while i < len(q) and q[i] not in "()|- ":
                    i += 1
                tokens.append(("TERM", q[start:i]))
        return tokens

    def _peek(self):
        """Return the current token without consuming it, or None if at end."""
        return (
            self.tokens[self.token_pos] if self.token_pos < len(self.tokens) else None
        )

    def _consume(self, expected_type=None):
        """Consume and return the current token if it matches expected_type.

        If expected_type is None, consume any token. Returns the consumed token or None.
        """
        tok = self._peek()
        if tok and (expected_type is None or tok[0] == expected_type):
            self.token_pos += 1
            return tok
        return None

    def parse(self) -> tuple[list[ASTNode], list[ASTNode]]:
        """Parse the token stream and return (inclusions, exclusions).

        Returns:
            A tuple (inclusions, exclusions) where:
              - inclusions: list of ASTNode patterns that must be present
              - exclusions: list of ASTNode patterns that must NOT be present

        Exclusions are indicated in the query by a leading '-' before an expression.
        """
        inclusions: list[ASTNode] = []
        exclusions: list[ASTNode] = []

        while self._peek():
            tok = self._peek()
            if tok[0] == "EXCLUDE":
                # Parse an exclusion expression: '-' followed by an expression
                self._consume("EXCLUDE")
                excl = self._parse_or_expr()
                if excl:
                    exclusions.append(Exclusion(excl))
            else:
                # Parse an inclusion expression
                inc = self._parse_or_expr()
                if inc:
                    inclusions.append(inc)
        return inclusions, exclusions

    # Grammar:
    # or_expr := and_expr ( 'OR' and_expr )*
    # and_expr := term ( term )*   # adjacency = Sequence (AND)
    # term := 'TERM' | '(' or_expr ')'

    def _parse_or_expr(self) -> ASTNode:
        """Parse OR expressions (left-associative)."""
        left = self._parse_and_expr()
        while self._peek() and self._peek()[0] == "OR":
            self._consume("OR")
            right = self._parse_and_expr()
            left = OrOperation(left, right)
        return left

    def _parse_and_expr(self) -> ASTNode:
        """Parse adjacency / AND sequences: collects neighboring terms into a Sequence."""
        first = self._parse_term()
        elems = [first] if first is not None else []
        while True:
            tok = self._peek()
            # Stop if next token ends the sequence context
            if not tok or tok[0] in ("OR", "GROUP_END", "EXCLUDE"):
                break
            nxt = self._parse_term()
            if nxt is None:
                break
            elems.append(nxt)
        if len(elems) == 1:
            return elems[0]
        return Sequence(elems)

    def _parse_term(self) -> ASTNode | None:
        """Parse a single term or parenthesized group.

        Returns:
            ASTNode for a TERM, GROUP_START...GROUP_END result, or None if nothing parsed.
        """
        tok = self._peek()
        if not tok:
            return None
        if tok[0] == "TERM":
            self._consume("TERM")
            val = tok[1]
            if "*" in val:
                # Term contains wildcard(s)
                return Wildcard(val)
            return ExactMatch(val)
        if tok[0] == "GROUP_START":
            # Parse grouped subexpression
            self._consume("GROUP_START")
            inner = self._parse_or_expr()
            if self._peek() and self._peek()[0] == "GROUP_END":
                self._consume("GROUP_END")
            return inner
        # Unexpected token: consume and ignore it, returning None
        self._consume()
        return None


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
        # If pattern does not start with '*' (i.e., anchored at left), add word boundary
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
    if query is None:
        return False
    clean = query.strip().strip("\"'")
    if clean == "":
        return False

    try:
        parser = PatternParser(clean)
        inclusions, exclusions = parser.parse()

        # First handle exclusions: if any exclusion matches -> overall False
        for excl in exclusions:
            excl_patterns = patterns_for_node(excl)
            for pat in excl_patterns:
                if pat and re.search(pat, text, flags=re.IGNORECASE | re.UNICODE):
                    return False

        # Then handle inclusions: each inclusion expression requires all its
        # sub-patterns to be present somewhere in the text (unordered).
        # For OrOperation inclusion, patterns_for_node returns a single OR pattern.
        for inc in inclusions:
            required = patterns_for_node(inc)
            if not required:
                # Empty inclusion considered non-matching
                return False
            all_found = True
            for pat in required:
                if not pat:
                    all_found = False
                    break
                if not re.search(pat, text, flags=re.IGNORECASE | re.UNICODE):
                    all_found = False
                    break
            if not all_found:
                return False

        # If there were any inclusions and they all passed -> True.
        # If no inclusions but exclusions existed (and none matched) -> True.
        return len(inclusions) > 0 or len(exclusions) > 0

    except Exception as e:
        # Log any parsing or runtime error with full traceback for diagnostics.
        # Using logger.exception automatically includes the stack trace,
        # which helps identify malformed query syntax or unexpected parsing errors.
        # The function still returns False to fail safely without raising.
        logger.exception(
            f"Error while evaluating search_match for query '{query}': {e}"
        )
        return False

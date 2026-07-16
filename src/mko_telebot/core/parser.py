"""Pattern parser module for building AST from query strings.

This module contains the PatternParser class and parse_query function
for parsing search query expressions.
"""

from enum import StrEnum

from .ast_nodes import ASTNode, ExactMatch, OrOperation, Sequence, Wildcard, Exclusion


class TokenType(StrEnum):
    """Token types for pattern query parsing.

    Provides type safety for token type strings in the parser.
    """

    GROUP_START = "GROUP_START"
    GROUP_END = "GROUP_END"
    OR = "OR"
    EXCLUDE = "EXCLUDE"
    TERM = "TERM"


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
        self.tokens: list[tuple[TokenType, str]] = self._tokenize()
        self.token_pos = 0

    def _tokenize(self) -> list[tuple[TokenType, str]]:
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
                tokens.append((TokenType.GROUP_START, "("))
                i += 1
            elif ch == ")":
                tokens.append((TokenType.GROUP_END, ")"))
                i += 1
            elif ch == "|":
                tokens.append((TokenType.OR, "|"))
                i += 1
            elif ch == "-":
                tokens.append((TokenType.EXCLUDE, "-"))
                i += 1
            elif ch.isspace():
                # Space serves as a separator (AND), tokens for spaces are not needed.
                i += 1
            else:
                # TERM: read until special character or whitespace
                start = i
                while i < len(q) and q[i] not in "()|- ":
                    i += 1
                tokens.append((TokenType.TERM, q[start:i]))
        return tokens

    def _peek(self) -> tuple[TokenType, str] | None:
        """Return the current token without consuming it, or None if at end."""
        return (
            self.tokens[self.token_pos] if self.token_pos < len(self.tokens) else None
        )

    def _consume(self, expected_type: TokenType | str | None = None) -> tuple[TokenType, str] | None:
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
            if tok and tok[0] == TokenType.EXCLUDE:
                # Parse an exclusion expression: '-' followed by an expression
                self._consume(TokenType.EXCLUDE)
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
        while (tok := self._peek()) and tok[0] == TokenType.OR:
            self._consume(TokenType.OR)
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
            if not tok or tok[0] in (TokenType.OR, TokenType.GROUP_END, TokenType.EXCLUDE):
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
        if tok[0] == TokenType.TERM:
            self._consume(TokenType.TERM)
            val = tok[1]
            if "*" in val:
                # Term contains wildcard(s)
                return Wildcard(val)
            return ExactMatch(val)
        if tok[0] == TokenType.GROUP_START:
            # Parse grouped subexpression
            self._consume(TokenType.GROUP_START)
            inner = self._parse_or_expr()
            if (tok := self._peek()) and tok[0] == TokenType.GROUP_END:
                self._consume(TokenType.GROUP_END)
            return inner
        # Unexpected token: consume and ignore it, returning None
        self._consume()
        return None


def parse_query(query: str) -> tuple[list[ASTNode], list[ASTNode]]:
    """Parse query into inclusion and exclusion AST node lists.

    Args:
        query: The raw query string to parse.

    Returns:
        A tuple (inclusions, exclusions) where:
          - inclusions: list of ASTNode patterns that must be present
          - exclusions: list of ASTNode patterns that must NOT be present

    Raises:
        ValueError: If query is None or empty after cleaning.
    """
    if query is None:
        raise ValueError("Query cannot be None")
    clean = query.strip().strip("\"'")
    if clean == "":
        raise ValueError("Query cannot be empty")

    parser = PatternParser(clean)
    return parser.parse()


__all__ = ["TokenType", "PatternParser", "parse_query"]
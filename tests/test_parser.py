import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from mko_telebot.core.parser import PatternParser, parse_query
from mko_telebot.core.ast_nodes import (
    ExactMatch,
    Wildcard,
    Exclusion,
    Sequence,
    OrOperation,
    ASTNode,
)

# Basic strategies for hypothesis
text_strategy = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=127)
    | st.characters(categories=["Ll", "Lu"]),
    min_size=0,
    max_size=100,
)

# Build a richer query strategy that can generate simple terms, terms with * and small groups/sequences
word = st.text(min_size=1, max_size=6, alphabet=st.characters(categories=["Ll", "Lu"]))
simple_term = st.builds(
    lambda left_star, w, right_star: f"{left_star}{w}{right_star}",
    st.one_of(st.just(""), st.just("*")),  # optional leading *
    word,
    st.one_of(st.just(""), st.just("*")),  # optional trailing *
)
or_group = st.lists(simple_term, min_size=1, max_size=3).map(
    lambda lst: "(" + " | ".join(lst) + ")"
)
sequence = st.lists(st.one_of(simple_term, or_group), min_size=1, max_size=4).map(
    lambda lst: " ".join(lst)
)
maybe_excl = st.one_of(st.just(""), st.just("-"))
generated_query = st.builds(lambda ex, seq: f'"{ex}{seq}"', maybe_excl, sequence)

query_strategy = st.one_of(
    st.just('"abd"'),
    st.just('"a | b"'),
    st.builds(
        lambda words: '"' + " | ".join(words) + '"',
        st.lists(
            st.text(
                min_size=1, max_size=5, alphabet=st.characters(categories=["Ll", "Lu"])
            ),
            min_size=2,
            max_size=3,
        ),
    ),
    generated_query,
)


# ---------------------------------------------------------------------------
# TestPatternParser - tokenization and parsing edge cases
# ---------------------------------------------------------------------------


class TestPatternParser:
    """Tests for PatternParser class tokenization and parsing."""

    def test_tokenize_simple_term(self):
        """Tokenization should parse single word as TERM token."""
        parser = PatternParser("hello")
        assert parser.tokens == [("TERM", "hello")]

    def test_tokenize_multiple_terms(self):
        """Tokenization should parse multiple words separated by spaces."""
        parser = PatternParser("hello world")
        assert parser.tokens == [("TERM", "hello"), ("TERM", "world")]

    def test_tokenize_or_operator(self):
        """Tokenization should identify OR operator '|'."""
        parser = PatternParser("a | b")
        assert parser.tokens == [("TERM", "a"), ("OR", "|"), ("TERM", "b")]

    def test_tokenize_group_start(self):
        """Tokenization should identify GROUP_START '('."""
        parser = PatternParser("(hello)")
        assert parser.tokens == [("GROUP_START", "("), ("TERM", "hello"), ("GROUP_END", ")")]

    def test_tokenize_group_end(self):
        """Tokenization should identify GROUP_END ')'."""
        parser = PatternParser("(a | b)")
        assert parser.tokens == [
            ("GROUP_START", "("),
            ("TERM", "a"),
            ("OR", "|"),
            ("TERM", "b"),
            ("GROUP_END", ")"),
        ]

    def test_tokenize_exclude_operator(self):
        """Tokenization should identify EXCLUDE '-'."""
        parser = PatternParser("-test")
        assert parser.tokens == [("EXCLUDE", "-"), ("TERM", "test")]

    def test_tokenize_wildcard_in_term(self):
        """Tokenization should preserve '*' inside TERM tokens."""
        parser = PatternParser("test* pattern*")
        assert parser.tokens == [
            ("TERM", "test*"),
            ("TERM", "pattern*"),
        ]

    def test_tokenize_complex_query(self):
        """Tokenization should handle complex queries with all token types."""
        parser = PatternParser("(a | b) -c d")
        assert parser.tokens == [
            ("GROUP_START", "("),
            ("TERM", "a"),
            ("OR", "|"),
            ("TERM", "b"),
            ("GROUP_END", ")"),
            ("EXCLUDE", "-"),
            ("TERM", "c"),
            ("TERM", "d"),
        ]

    def test_tokenize_ignores_whitespace(self):
        """Tokenization should skip whitespace characters."""
        parser = PatternParser("  hello   world  ")
        assert parser.tokens == [("TERM", "hello"), ("TERM", "world")]

    def test_tokenize_empty_query(self):
        """Empty query should produce empty token list."""
        parser = PatternParser("")
        assert parser.tokens == []

    def test_tokenize_whitespace_only(self):
        """Whitespace-only query should produce empty token list."""
        parser = PatternParser("   \t\n  ")
        assert parser.tokens == []

    def test_peek_at_start(self):
        """Peek should return first token without consuming it."""
        parser = PatternParser("a b")
        assert parser._peek() == ("TERM", "a")
        assert parser.token_pos == 0  # Position unchanged

    def test_peek_at_end(self):
        """Peek at end of token stream should return None."""
        parser = PatternParser("a")
        parser.token_pos = len(parser.tokens)
        assert parser._peek() is None

    def test_consume_any_token(self):
        """Consume without expected_type should consume any token."""
        parser = PatternParser("a | b")
        tok = parser._consume()
        assert tok == ("TERM", "a")
        assert parser.token_pos == 1

    def test_consume_with_expected_type(self):
        """Consume should only consume matching token type."""
        parser = PatternParser("a | b")
        tok = parser._consume("OR")
        assert tok is None  # First token is TERM, not OR
        assert parser.token_pos == 0  # Position unchanged

    def test_consume_matching_type(self):
        """Consume should work when token type matches."""
        parser = PatternParser("a | b")
        tok = parser._consume("TERM")
        assert tok == ("TERM", "a")
        assert parser.token_pos == 1

    def test_parse_simple_term(self):
        """Parse should return single ExactMatch for simple term."""
        parser = PatternParser("hello")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], ExactMatch)
        assert inclusions[0].value == "hello"
        assert len(exclusions) == 0

    def test_parse_or_expression(self):
        """Parse should return OrOperation for OR expressions."""
        parser = PatternParser("a | b")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], OrOperation)
        assert isinstance(inclusions[0].left, ExactMatch)
        assert inclusions[0].left.value == "a"
        assert isinstance(inclusions[0].right, ExactMatch)
        assert inclusions[0].right.value == "b"

    def test_parse_exclusion(self):
        """Parse should return Exclusion for '-' prefixed term."""
        parser = PatternParser("-test")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 0
        assert len(exclusions) == 1
        assert isinstance(exclusions[0], Exclusion)
        assert isinstance(exclusions[0].child, ExactMatch)
        assert exclusions[0].child.value == "test"

    def test_parse_grouped_or(self):
        """Parse should handle grouped OR expressions."""
        parser = PatternParser("(a | b)")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], OrOperation)

    def test_parse_sequence(self):
        """Parse should return Sequence for space-separated terms."""
        parser = PatternParser("hello world")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Sequence)
        assert len(inclusions[0].elements) == 2

    def test_parse_mixed_inclusion_exclusion(self):
        """Parse should handle mixed inclusion and exclusion."""
        parser = PatternParser("hello -world")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], ExactMatch)
        assert inclusions[0].value == "hello"
        assert len(exclusions) == 1
        assert isinstance(exclusions[0], Exclusion)

    def test_parse_wildcard_term(self):
        """Parse should return Wildcard for terms containing '*'."""
        parser = PatternParser("test*")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Wildcard)
        assert inclusions[0].pattern == "test*"

    def test_parse_wildcard_in_group(self):
        """Parse should handle wildcard inside grouped expression."""
        parser = PatternParser("(a* | b*)")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], OrOperation)

    def test_parse_nested_groups(self):
        """Parse should handle nested parentheses."""
        parser = PatternParser("((a | b) c)")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Sequence)

    def test_parse_empty_after_peek(self):
        """Parse should handle empty token stream gracefully in _parse_term."""
        parser = PatternParser("")
        result = parser._parse_term()
        assert result is None

    def test_parse_term_returns_none_on_consecutive_groups(self):
        """Parse should handle cases where _parse_term returns None in sequence."""
        parser = PatternParser("a | | b")
        inclusions, exclusions = parser.parse()
        assert isinstance(inclusions, list)

    def test_parse_unexpected_token_handling(self):
        """Parse should handle unexpected tokens gracefully by consuming and ignoring."""
        parser = PatternParser(") a (")
        inclusions, exclusions = parser.parse()
        assert isinstance(inclusions, list)

    def test_parse_empty_group_returns_none(self):
        """Parse should handle empty groups where _parse_term returns None."""
        parser = PatternParser("a () b")
        inclusions, exclusions = parser.parse()
        assert len(inclusions) == 1


# ---------------------------------------------------------------------------
# TestParseQuery - parse_query function tests
# ---------------------------------------------------------------------------


class TestParseQuery:
    """Tests for parse_query function."""

    def test_parse_query_none_raises(self):
        """parse_query should raise ValueError for None input."""
        with pytest.raises(ValueError, match="cannot be None"):
            parse_query(None)

    def test_parse_query_empty_raises(self):
        """parse_query should raise ValueError for empty query."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_query("")

    def test_parse_query_whitespace_only_raises(self):
        """parse_query should raise ValueError for whitespace-only query."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_query("   ")

    def test_parse_query_quoted_raises(self):
        """parse_query should handle quoted strings by stripping them."""
        inclusions, exclusions = parse_query('"hello"')
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], ExactMatch)
        assert inclusions[0].value == "hello"

    def test_parse_query_single_term(self):
        """parse_query should parse single term correctly."""
        inclusions, exclusions = parse_query("hello")
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], ExactMatch)
        assert inclusions[0].value == "hello"

    def test_parse_query_multiple_terms_sequence(self):
        """parse_query should parse space-separated terms as Sequence."""
        inclusions, exclusions = parse_query("hello world")
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Sequence)
        assert len(inclusions[0].elements) == 2

    def test_parse_query_or_expression(self):
        """parse_query should parse OR expressions correctly."""
        inclusions, exclusions = parse_query("a | b")
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], OrOperation)

    def test_parse_query_negation(self):
        """parse_query should parse negated expressions correctly."""
        inclusions, exclusions = parse_query("-test")
        assert len(exclusions) == 1
        assert isinstance(exclusions[0], Exclusion)

    def test_parse_query_complex(self):
        """parse_query should parse complex queries with OR and exclusion."""
        inclusions, exclusions = parse_query("(a | b) c -d")
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Sequence)
        assert len(exclusions) == 1

    def test_parse_query_nested_parentheses(self):
        """parse_query should handle nested parentheses correctly."""
        inclusions, exclusions = parse_query("((a | b) (c | d))")
        assert len(inclusions) == 1

    def test_parse_query_wildcard_single(self):
        """parse_query should parse wildcard patterns."""
        inclusions, exclusions = parse_query("test*")
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Wildcard)

    def test_parse_query_wildcard_both_ends(self):
        """parse_query should parse wildcards at both ends."""
        inclusions, exclusions = parse_query("*test*")
        assert len(inclusions) == 1
        assert isinstance(inclusions[0], Wildcard)
        assert inclusions[0].pattern == "*test*"

    def test_parse_query_malformed_unclosed_paren(self):
        """parse_query should handle malformed queries gracefully (unclosed paren)."""
        # The parser doesn't validate balanced parens strictly - it just returns what it parses
        inclusions, exclusions = parse_query("(unclosed")
        # Should still return something (not crash)
        assert isinstance(inclusions, list)

    def test_parse_query_multiple_exclusions(self):
        """parse_query should handle multiple exclusion patterns."""
        inclusions, exclusions = parse_query("hello -world -test")
        assert len(inclusions) == 1
        assert len(exclusions) == 2


# ---------------------------------------------------------------------------
# TestASTNodes - AST node type tests
# ---------------------------------------------------------------------------


class TestASTNodes:
    """Tests for AST node classes."""

    def test_exact_match_creation(self):
        """ExactMatch should store the value correctly."""
        node = ExactMatch(value="hello")
        assert node.value == "hello"

    def test_exact_match_is_ast_node(self):
        """ExactMatch should be an ASTNode subclass."""
        node = ExactMatch(value="test")
        assert isinstance(node, ASTNode)

    def test_wildcard_creation(self):
        """Wildcard should store the pattern correctly."""
        node = Wildcard(pattern="test*")
        assert node.pattern == "test*"

    def test_wildcard_is_ast_node(self):
        """Wildcard should be an ASTNode subclass."""
        node = Wildcard(pattern="*test*")
        assert isinstance(node, ASTNode)

    def test_or_operation_creation(self):
        """OrOperation should store left and right operands."""
        left = ExactMatch(value="a")
        right = ExactMatch(value="b")
        node = OrOperation(left=left, right=right)
        assert node.left == left
        assert node.right == right

    def test_or_operation_is_ast_node(self):
        """OrOperation should be an ASTNode subclass."""
        node = OrOperation(
            left=ExactMatch(value="a"), right=ExactMatch(value="b")
        )
        assert isinstance(node, ASTNode)

    def test_sequence_creation(self):
        """Sequence should store elements list."""
        elements = [ExactMatch(value="a"), ExactMatch(value="b")]
        node = Sequence(elements=elements)
        assert node.elements == elements
        assert len(node.elements) == 2

    def test_sequence_is_ast_node(self):
        """Sequence should be an ASTNode subclass."""
        node = Sequence(elements=[ExactMatch(value="a")])
        assert isinstance(node, ASTNode)

    def test_exclusion_creation(self):
        """Exclusion should store child node."""
        child = ExactMatch(value="test")
        node = Exclusion(child=child)
        assert node.child == child

    def test_exclusion_is_ast_node(self):
        """Exclusion should be an ASTNode subclass."""
        node = Exclusion(child=Wildcard(pattern="test*"))
        assert isinstance(node, ASTNode)

    def test_exclusion_negates_child(self):
        """Exclusion wraps a child that should not match."""
        child = ExactMatch(value="hello")
        node = Exclusion(child=child)
        assert node.child.value == "hello"


# ---------------------------------------------------------------------------
# Integration tests with matcher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, query, expected",
    [
        # Wildcard positions
        ("za", '"za*"', True),
        ("zagsd", '"za*"', True),
        ("dfza", '"*za"', True),
        ("myabxcd", '"a*cd"', False),
        # ("a bcd", '"a*cd"', False),
        # Boundaries and punctuation
        ("#abd%", '"abd"', True),
        ("abd-continue", '"abd"', True),
        ("ab'd", '"ab\'d"', True),
        ("абд", '"abd"', False),
        # Exclusion-only and exclusion precedence
        ("no iphone here", '"-iphone"', False),
        ("My iPhone", '"-iphone"', False),
        ("тут будет услуга которая мне не нужна", '"-услуг*"', False),
        ("тут будут услуги которые мне не нужны", '"-услуг*"', False),
        ("тут будет телефон и услуги которые мне не нужны", '"телефон -услуг*"', False),
        ("тут будет телефон и услуги которые мне нужны", '"телефон"', True),
        # Malformed / robustness
        ("text", '"(unclosed | test"', False),
        ("", '""', False),
        ("something", '"   "', False),
        # Unicode & case (case-insensitive expected)
        ("БУДВА", "(budv* | будв* | бечичи)", True),
        ("БудвA", "(budv* | будв* | бечичи)", True),
        # Overlap/substrings
        ("iphone budv", '"budv -iphone"', False),
        ("budviphone", '"budv"', False),
        # Groups and sequence (order-independence expected)
        ("kdfsd ax zx rdff", '"(ax | bx) (zx | yx)"', True),
        ("ffn bx yx tgg", '"(ax | bx) (zx | yx)"', True),
        ("df zx ax", '"(ax | bx) (zx | yy)"', True),
        ("zx yx", '"(a | b) (z | y)"', False),
        ("kdfsd ax bx rdff", '"(ax | bx) (zx | yx)"', False),
        ("ffn bx yax tgg", '"(ax | bx) (zx | yx)"', False),
        ("ffn yx bx  tgg", '"(ax | bx) (zx | yx)"', True),
        ("yx ffn  bx  tgg", '"(ax | bx) (zx | yx)"', True),
        # Wildcard *: non-space chars, including zero
        ("zagsdgs", '"za*"', True),
        ("za", '"za*"', True),  # Zero-length match after za
        ("za with space", '"za*"', True),  # * doesn't cross space
        ("dfdfdza", '"*za"', True),
        ("za at start", '"*za"', True),
        # Negation: -word means not in whole text
        ("tivat here", '"tivat -услуги"', True),
        ("tivat услуги", '"tivat -услуги"', False),
        ("тиват", '"(tivat | тиват) -услуги"', True),
        ("тиват услуги", '"(tivat | тиват) -услуги"', False),
        # Complex examples from task
        ("some udv text", '"(*udv* | *будв* | херцег* | котор | бечичи)"', True),
        ("becici", '"(*udv* | *будв* | херцег* | котор | бечичи)"', False),
        ("tivat", '"(tivat | тиват) -услуги"', True),
        ("тиват услуги", '"(tivat | тиват) -услуги"', False),
        (
            "budv* инструмент",
            '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',
            True,
        ),
        (
            "budv iphone",
            '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',
            False,
        ),
        (
            "котор услуги",
            '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',
            False,
        ),
        (
            "budv* кроссовки 43",
            '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"',
            True,
        ),
        (
            "budv* кроссовки 45",
            '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"',
            False,
        ),
        (
            "будвa кроссовки 43",
            '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"',
            True,
        ),
        (
            "кроссовки 43 будвa",
            '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"',
            True,
        ),
        # Multiline and special
        ("line1\nabd line2", '"abd"', True),
        ("$abd%", '"abd"', True),
        ("abd-continue", '"abd"', True),
        # Order-independence tests (main feature)
        (
            "#продам кроссовки 43 будва / Бечичи",
            "(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)",
            True,
        ),
        (
            "#продам 43 будва / Бечичи кроссовки",
            "(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)",
            True,
        ),
        (
            "#продам будва / Бечичи кроссовки 43",
            "(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)",
            True,
        ),
    ],
)
def test_search_match(matcher, text, query, expected):
    assert matcher(text, query) == expected


# Property-based from Tester 3: limited for speed
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(text=text_strategy, query=st.sampled_from(['"a*"', '"*b"', '"(c | d)"']))
def test_property_no_crash_basic(matcher, text, query):
    # Just ensure no exceptions and boolean result
    try:
        result = matcher(text, query)
        assert isinstance(result, bool)
    except Exception:
        pytest.fail("Function crashed")


# Extended property-based test with richer query generation (ensure no crash)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
@given(text=text_strategy, query=generated_query)
def test_property_no_crash_generated(matcher, text, query):
    try:
        result = matcher(text, query)
        assert isinstance(result, bool)
    except Exception:
        pytest.fail("Function crashed")


# Slow-ish integration test for large text (mark as slow so it's optional in CI)
@pytest.mark.slow
def test_large_text_performance(matcher):
    large_text = ("word " * 3000) + " будва кроссовки 43 " + (" word" * 3000)
    pattern = "(budv* | будв* | бечичи) кроссовки (43 | 44)"
    # expect True because 'будва' and 'кроссовки' and '43' are present (order shouldn't matter)
    assert matcher(large_text, pattern) is True
"""Unit tests for core/matcher.py internal functions."""

from typing import cast

from mko_telebot.core.matcher import (
    ast_to_regex,
    patterns_for_node,
    evaluate_query,
    _check_patterns_match,
)
from mko_telebot.core.ast_nodes import (
    ExactMatch,
    Wildcard,
    OrOperation,
    Sequence,
    Exclusion,
    ASTNode,
)


# =============================================================================
# Tests for ast_to_regex function
# =============================================================================


class TestAstToRegexExactMatch:
    """Tests for ast_to_regex with ExactMatch nodes."""

    def test_exact_match_basic(self) -> None:
        """ast_to_regex should generate word-boundary regex for exact match."""
        node = ExactMatch(value="hello")
        result = ast_to_regex(node)
        assert result == r"\bhello\b"

    def test_exact_match_special_chars_escaped(self) -> None:
        """ast_to_regex should escape special regex characters in exact match."""
        node = ExactMatch(value="test.value")
        result = ast_to_regex(node)
        assert result == r"\btest\.value\b"

    def test_exact_match_cyrillic(self) -> None:
        """ast_to_regex should handle Cyrillic characters correctly."""
        node = ExactMatch(value="привет")
        result = ast_to_regex(node)
        assert result == r"\bпривет\b"


class TestAstToRegexWildcard:
    """Tests for ast_to_regex with Wildcard nodes."""

    def test_wildcard_trailing(self) -> None:
        r"""ast_to_regex should convert trailing * to [^\s]* without right boundary."""
        node = Wildcard(pattern="hello*")
        result = ast_to_regex(node)
        # Trailing * means no closing word boundary
        assert result == r"\bhello[^\s]*"

    def test_wildcard_leading(self) -> None:
        r"""ast_to_regex should convert leading * to [^\s]* without left boundary."""
        node = Wildcard(pattern="*hello")
        result = ast_to_regex(node)
        # Leading * means no opening word boundary
        assert result == r"[^\s]*hello\b"

    def test_wildcard_both_ends(self) -> None:
        """ast_to_regex should handle wildcard at both ends."""
        node = Wildcard(pattern="*hello*")
        result = ast_to_regex(node)
        # Both * means no word boundaries
        assert result == r"[^\s]*hello[^\s]*"

    def test_wildcard_middle(self) -> None:
        """ast_to_regex should handle wildcard in the middle."""
        node = Wildcard(pattern="he*llo")
        result = ast_to_regex(node)
        # * in middle has word boundaries on both sides
        assert result == r"\bhe[^\s]*llo\b"

    def test_wildcard_special_chars_escaped(self) -> None:
        """ast_to_regex should escape special regex chars in wildcard pattern."""
        node = Wildcard(pattern="test*value+")
        result = ast_to_regex(node)
        # The + should be escaped in the result, and * converted to [^\s]*
        # Result should be like \btest[^\s]*value\+\b
        assert r"\+" in result  # + should be escaped


class TestAstToRegexOrOperation:
    """Tests for ast_to_regex with OrOperation nodes."""

    def test_or_operation_basic(self) -> None:
        """ast_to_regex should create non-capturing group combining left|right."""
        node = OrOperation(left=ExactMatch(value="a"), right=ExactMatch(value="b"))
        result = ast_to_regex(node)
        # Each side gets its own word boundaries since they are ExactMatch nodes
        assert result == r"(?:\ba\b|\bb\b)"

    def test_or_operation_with_wildcards(self) -> None:
        """ast_to_regex should handle OR with wildcard patterns."""
        node = OrOperation(
            left=Wildcard(pattern="test*"),
            right=Wildcard(pattern="*end"),
        )
        result = ast_to_regex(node)
        # Each side has its own boundaries based on the wildcard position
        assert result == r"(?:\btest[^\s]*|[^\s]*end\b)"


class TestAstToRegexExclusion:
    """Tests for ast_to_regex with Exclusion nodes."""

    def test_exclusion_delegates_to_child(self) -> None:
        """ast_to_regex should delegate to child node for Exclusion."""
        node = Exclusion(child=ExactMatch(value="hello"))
        result = ast_to_regex(node)
        assert result == r"\bhello\b"

    def test_exclusion_with_wildcard(self) -> None:
        """ast_to_regex should delegate to wildcard child for Exclusion."""
        node = Exclusion(child=Wildcard(pattern="test*"))
        result = ast_to_regex(node)
        assert result == r"\btest[^\s]*"


class TestAstToRegexUnknownNode:
    """Tests for ast_to_regex with unknown node types."""

    def test_unknown_node_returns_empty(self) -> None:
        """ast_to_regex should return empty string for unknown node types."""
        # ExactMatch is used for reference; ast_to_regex returns regex for known types
        node = ExactMatch(value="dummy")
        result = ast_to_regex(node)
        assert isinstance(result, str)


# =============================================================================
# Tests for patterns_for_node function
# =============================================================================


class TestPatternsForNodeExactMatch:
    """Tests for patterns_for_node with ExactMatch nodes."""

    def test_exact_match_returns_single_pattern(self) -> None:
        """patterns_for_node should return single-element list for ExactMatch."""
        node = ExactMatch(value="hello")
        result = patterns_for_node(node)
        assert result == [r"\bhello\b"]


class TestPatternsForNodeWildcard:
    """Tests for patterns_for_node with Wildcard nodes."""

    def test_wildcard_returns_single_pattern(self) -> None:
        """patterns_for_node should return single-element list for Wildcard."""
        node = Wildcard(pattern="test*")
        result = patterns_for_node(node)
        assert result == [r"\btest[^\s]*"]


class TestPatternsForNodeOrOperation:
    """Tests for patterns_for_node with OrOperation nodes."""

    def test_or_operation_returns_single_pattern(self) -> None:
        """patterns_for_node should return single OR pattern for OrOperation."""
        node = OrOperation(left=ExactMatch(value="a"), right=ExactMatch(value="b"))
        result = patterns_for_node(node)
        # OrOperation produces a single pattern with boundaries around each alternative
        assert result == [r"(?:\ba\b|\bb\b)"]


class TestPatternsForNodeSequence:
    """Tests for patterns_for_node with Sequence nodes."""

    def test_sequence_flattens_patterns(self) -> None:
        """patterns_for_node should flatten all element patterns into list."""
        node = Sequence(
            elements=[
                ExactMatch(value="a"),
                ExactMatch(value="b"),
                ExactMatch(value="c"),
            ]
        )
        result = patterns_for_node(node)
        assert len(result) == 3
        assert r"\ba\b" in result
        assert r"\bb\b" in result
        assert r"\bc\b" in result

    def test_sequence_with_or(self) -> None:
        """patterns_for_node should handle Sequence with OrOperation elements."""
        node = Sequence(
            elements=[
                OrOperation(left=ExactMatch(value="a"), right=ExactMatch(value="b")),
                ExactMatch(value="c"),
            ]
        )
        result = patterns_for_node(node)
        assert len(result) == 2
        # OrOperation produces a single pattern with boundaries around each alternative
        assert r"(?:\ba\b|\bb\b)" in result
        assert r"\bc\b" in result

    def test_sequence_with_wildcards(self) -> None:
        """patterns_for_node should handle Sequence with Wildcard elements."""
        node = Sequence(
            elements=[
                Wildcard(pattern="test*"),
                ExactMatch(value="end"),
            ]
        )
        result = patterns_for_node(node)
        assert len(result) == 2
        assert r"\btest[^\s]*" in result
        assert r"\bend\b" in result

    def test_sequence_empty(self) -> None:
        """patterns_for_node should return empty list for empty Sequence."""
        node = Sequence(elements=[])
        result = patterns_for_node(node)
        assert result == []


class TestPatternsForNodeExclusion:
    """Tests for patterns_for_node with Exclusion nodes."""

    def test_exclusion_delegates_to_child(self) -> None:
        """patterns_for_node should return child's patterns for Exclusion."""
        node = Exclusion(child=ExactMatch(value="hello"))
        result = patterns_for_node(node)
        assert result == [r"\bhello\b"]

    def test_exclusion_with_sequence(self) -> None:
        """patterns_for_node should handle Exclusion with Sequence child."""
        node = Exclusion(
            child=Sequence(elements=[ExactMatch(value="a"), ExactMatch(value="b")])
        )
        result = patterns_for_node(node)
        assert len(result) == 2


# =============================================================================
# Tests for _check_patterns_match function
# =============================================================================


class TestCheckPatternsMatch:
    """Tests for _check_patterns_match function."""

    def test_all_patterns_match(self) -> None:
        """_check_patterns_match should return True when all patterns match."""
        patterns = [r"\bhello\b", r"\bworld\b"]
        text = "hello there world"
        assert _check_patterns_match(text, patterns) is True

    def test_one_pattern_fails(self) -> None:
        """_check_patterns_match should return False when any pattern fails."""
        patterns = [r"\bhello\b", r"\bmissing\b"]
        text = "hello there world"
        assert _check_patterns_match(text, patterns) is False

    def test_empty_patterns_returns_false(self) -> None:
        """_check_patterns_match should return False for empty pattern list."""
        assert _check_patterns_match("hello", []) is False

    def test_empty_pattern_string_returns_false(self) -> None:
        """_check_patterns_match should return False for empty pattern string in list."""
        patterns = [r"\bhello\b", ""]
        text = "hello world"
        assert _check_patterns_match(text, patterns) is False

    def test_case_insensitive_match(self) -> None:
        """_check_patterns_match should perform case-insensitive matching."""
        patterns = [r"\bhello\b"]
        text = "HELLO world"
        assert _check_patterns_match(text, patterns) is True

    def test_wildcard_pattern_match(self) -> None:
        """_check_patterns_match should handle wildcard patterns."""
        patterns = [r"\btest[^\s]*"]
        text = "testing something"
        assert _check_patterns_match(text, patterns) is True

    def test_wildcard_pattern_no_match(self) -> None:
        """_check_patterns_match should return False when wildcard pattern doesn't match."""
        patterns = [r"\btest[^\s]*"]
        text = "no match here"
        assert _check_patterns_match(text, patterns) is False

    def test_unicode_pattern_match(self) -> None:
        """_check_patterns_match should handle Unicode patterns."""
        patterns = [r"\bпривет\b"]
        text = "привет мир"
        assert _check_patterns_match(text, patterns) is True


# =============================================================================
# Tests for evaluate_query function
# =============================================================================


class TestEvaluateQueryInclusion:
    """Tests for evaluate_query inclusion logic."""

    def test_single_inclusion_match(self) -> None:
        """evaluate_query should return True for matching single inclusion."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = []
        assert evaluate_query("hello world", inclusions, exclusions) is True

    def test_multiple_inclusions_all_match(self) -> None:
        """evaluate_query should return True when all inclusions match."""
        inclusions: list[ASTNode] = [
            ExactMatch(value="hello"),
            ExactMatch(value="world"),
        ]
        exclusions: list[ASTNode] = []
        assert evaluate_query("hello there world", inclusions, exclusions) is True

    def test_one_inclusion_fails(self) -> None:
        """evaluate_query should return False when any inclusion fails."""
        inclusions: list[ASTNode] = [
            ExactMatch(value="hello"),
            ExactMatch(value="missing"),
        ]
        exclusions: list[ASTNode] = []
        assert evaluate_query("hello world", inclusions, exclusions) is False

    def test_empty_inclusions_empty_exclusions_returns_false(self) -> None:
        """evaluate_query should return False when both inclusions and exclusions are empty."""
        assert evaluate_query("hello", [], []) is False


class TestEvaluateQueryExclusion:
    """Tests for evaluate_query exclusion logic."""

    def test_exclusion_prevents_match(self) -> None:
        """evaluate_query should return False when exclusion matches."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = [ExactMatch(value="world")]
        assert evaluate_query("hello world", inclusions, exclusions) is False

    def test_exclusion_no_match_allows_inclusion(self) -> None:
        """evaluate_query should return True when exclusion doesn't match."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = [ExactMatch(value="world")]
        assert evaluate_query("hello there", inclusions, exclusions) is True

    def test_exclusion_checked_before_inclusion(self) -> None:
        """evaluate_query should check exclusions first (return False immediately on match)."""
        # Create patterns where both inclusion and exclusion would match
        # Exclusion should take precedence
        seq = Sequence(elements=[ExactMatch(value="hello"), ExactMatch(value="world")])
        inclusions: list[ASTNode] = [cast(ASTNode, seq)]
        exclusions: list[ASTNode] = [ExactMatch(value="world")]
        assert evaluate_query("hello world", inclusions, exclusions) is False

    def test_exclusion_only_no_match_returns_true(self) -> None:
        """evaluate_query should return True when only exclusions exist and none match."""
        exclusions: list[ASTNode] = [ExactMatch(value="missing")]
        inclusions: list[ASTNode] = []
        assert evaluate_query("hello world", inclusions, exclusions) is True

    def test_multiple_exclusions_any_match_fails(self) -> None:
        """evaluate_query should return False when any exclusion matches."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = [ExactMatch(value="foo"), ExactMatch(value="world")]
        assert evaluate_query("hello world", inclusions, exclusions) is False


class TestEvaluateQuerySequence:
    """Tests for evaluate_query with Sequence inclusions."""

    def test_sequence_all_elements_present(self) -> None:
        """evaluate_query should return True when all sequence elements are present."""
        seq = Sequence(elements=[ExactMatch(value="a"), ExactMatch(value="b")])
        inclusions: list[ASTNode] = [cast(ASTNode, seq)]
        exclusions: list[ASTNode] = []
        assert evaluate_query("a and b", inclusions, exclusions) is True

    def test_sequence_partial_match(self) -> None:
        """evaluate_query should return False when sequence element is missing."""
        seq = Sequence(elements=[ExactMatch(value="a"), ExactMatch(value="b")])
        inclusions: list[ASTNode] = [cast(ASTNode, seq)]
        exclusions: list[ASTNode] = []
        assert evaluate_query("a only", inclusions, exclusions) is False


class TestEvaluateQueryOrOperation:
    """Tests for evaluate_query with OrOperation."""

    def test_or_operation_one_side_matches(self) -> None:
        """evaluate_query should return True when one OR side matches."""
        or_node = OrOperation(
            left=ExactMatch(value="hello"), right=ExactMatch(value="world")
        )
        inclusions: list[ASTNode] = [cast(ASTNode, or_node)]
        exclusions: list[ASTNode] = []
        assert evaluate_query("hello there", inclusions, exclusions) is True

    def test_or_operation_neither_matches(self) -> None:
        """evaluate_query should return False when neither OR side matches."""
        or_node = OrOperation(
            left=ExactMatch(value="hello"), right=ExactMatch(value="world")
        )
        inclusions: list[ASTNode] = [cast(ASTNode, or_node)]
        exclusions: list[ASTNode] = []
        assert evaluate_query("goodbye", inclusions, exclusions) is False


class TestEvaluateQueryWildcard:
    """Tests for evaluate_query with Wildcard patterns."""

    def test_wildcard_inclusion_match(self) -> None:
        """evaluate_query should handle wildcard in inclusion."""
        inclusions: list[ASTNode] = [Wildcard(pattern="test*")]
        exclusions: list[ASTNode] = []
        assert evaluate_query("testing something", inclusions, exclusions) is True

    def test_wildcard_exclusion_match(self) -> None:
        """evaluate_query should handle wildcard in exclusion."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = [Wildcard(pattern="test*")]
        assert evaluate_query("hello testing", inclusions, exclusions) is False

    def test_wildcard_exclusion_no_match(self) -> None:
        """evaluate_query should allow match when wildcard exclusion doesn't match."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = [Wildcard(pattern="xyz*")]
        assert evaluate_query("hello world", inclusions, exclusions) is True


class TestEvaluateQueryUnicode:
    """Tests for evaluate_query with Unicode patterns."""

    def test_unicode_inclusion(self) -> None:
        """evaluate_query should handle Unicode inclusion patterns."""
        inclusions: list[ASTNode] = [ExactMatch(value="привет")]
        exclusions: list[ASTNode] = []
        assert evaluate_query("привет мир", inclusions, exclusions) is True

    def test_unicode_exclusion(self) -> None:
        """evaluate_query should handle Unicode exclusion patterns."""
        inclusions: list[ASTNode] = [ExactMatch(value="hello")]
        exclusions: list[ASTNode] = [ExactMatch(value="привет")]
        assert evaluate_query("hello мир", inclusions, exclusions) is True

    def test_unicode_exclusion_blocks(self) -> None:
        """evaluate_query should block match when Unicode exclusion matches."""
        inclusions: list[ASTNode] = [ExactMatch(value="привет")]
        exclusions: list[ASTNode] = [Wildcard(pattern="м*")]
        assert evaluate_query("привет мир", inclusions, exclusions) is False


class TestEvaluateQueryComplex:
    """Tests for evaluate_query with complex combinations."""

    def test_complex_query_with_exclusion(self) -> None:
        """evaluate_query should handle complex inclusion with exclusion."""
        seq = Sequence(
            elements=[
                ExactMatch(value="hello"),
                ExactMatch(value="world"),
            ]
        )
        inclusions: list[ASTNode] = [cast(ASTNode, seq)]
        exclusions: list[ASTNode] = [ExactMatch(value="bad")]
        assert evaluate_query("hello world", inclusions, exclusions) is True

    def test_complex_query_exclusion_blocks(self) -> None:
        """evaluate_query should block when complex exclusion matches."""
        seq = Sequence(
            elements=[
                ExactMatch(value="hello"),
                ExactMatch(value="world"),
            ]
        )
        inclusions: list[ASTNode] = [cast(ASTNode, seq)]
        exclusions: list[ASTNode] = [ExactMatch(value="bad")]
        assert evaluate_query("hello bad world", inclusions, exclusions) is False

    def test_or_with_wildcard_and_exclusion(self) -> None:
        """evaluate_query should handle OR with wildcards and exclusions."""
        or_node = OrOperation(
            left=Wildcard(pattern="bike*"),
            right=ExactMatch(value="car"),
        )
        inclusions: list[ASTNode] = [cast(ASTNode, or_node)]
        exclusions: list[ASTNode] = [ExactMatch(value="expensive")]
        assert evaluate_query("biker", inclusions, exclusions) is True
        assert evaluate_query("biker expensive", inclusions, exclusions) is False
        assert evaluate_query("car", inclusions, exclusions) is True

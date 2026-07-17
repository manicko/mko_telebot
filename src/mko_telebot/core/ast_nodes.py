"""AST node definitions for pattern matching parser.

This module contains the dataclass definitions for the abstract syntax tree
nodes used by the pattern parser to represent search queries.
"""

from dataclasses import dataclass


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

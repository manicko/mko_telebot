# -*- coding: utf-8 -*-
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

# Basic strategies for hypothesis
text_strategy = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=127) | st.characters(categories=['Ll', 'Lu']),
    min_size=0,
    max_size=100
)

# Build a richer query strategy that can generate simple terms, terms with * and small groups/sequences
word = st.text(min_size=1, max_size=6, alphabet=st.characters(categories=['Ll', 'Lu']))
simple_term = st.builds(
    lambda left_star, w, right_star: f'{left_star}{w}{right_star}',
    st.one_of(st.just(''), st.just('*')),  # optional leading *
    word,
    st.one_of(st.just(''), st.just('*'))   # optional trailing *
)
or_group = st.lists(simple_term, min_size=1, max_size=3).map(lambda lst: "(" + " | ".join(lst) + ")")
sequence = st.lists(st.one_of(simple_term, or_group), min_size=1, max_size=4).map(lambda lst: " ".join(lst))
maybe_excl = st.one_of(st.just(''), st.just('-'))
generated_query = st.builds(lambda ex, seq: f'"{ex}{seq}"', maybe_excl, sequence)

query_strategy = st.one_of(
    st.just('"abd"'),
    st.just('"a | b"'),
    st.builds(lambda words: '"' + " | ".join(words) + '"',
              st.lists(st.text(min_size=1, max_size=5, alphabet=st.characters(categories=['Ll', 'Lu'])),
                       min_size=2, max_size=3)),
    generated_query
)


@pytest.mark.parametrize("text, query, expected", [

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
    ("БУДВА", '(budv* | будв* | бечичи)', True),
    ("БудвA", '(budv* | будв* | бечичи)', True),

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
    ("budv* инструмент",
     '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',
     True),
    ("budv iphone",
     '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',
     False),
    ("котор услуги",
     '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',
     False),
    ("budv* кроссовки 43", '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"', True),
    ("budv* кроссовки 45", '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"', False),
    ("будвa кроссовки 43", '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"', True),
    ("кроссовки 43 будвa", '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"', True),

    # Multiline and special
    ("line1\nabd line2", '"abd"', True),
    ("$abd%", '"abd"', True),
    ("abd-continue", '"abd"', True),

    # Order-independence tests (main feature)
    ("#продам кроссовки 43 будва / Бечичи", '(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)', True),
    ("#продам 43 будва / Бечичи кроссовки", '(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)', True),
    ("#продам будва / Бечичи кроссовки 43", '(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)', True),

])
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
    pattern = '(budv* | будв* | бечичи) кроссовки (43 | 44)'
    # expect True because 'будва' and 'кроссовки' and '43' are present (order shouldn't matter)
    assert matcher(large_text, pattern) is True

import pytest

from src.mko_telebot.core.parser import search_match


@pytest.fixture
def matcher():
    return search_match


@pytest.fixture
def sample_queries():
    return [
        '"abd"',  # Basic word
        '"a | b"',  # OR
        '"(a | b) (z | y)"',  # Groups
        '"za*"',  # Wildcard
        '"tivat -услуги"',  # Negation
        '"(*udv* | *будв* | херцег* | котор | бечичи)"',  # Complex example
        '"(tivat | тиват) -услуги"',  # Mixed lang + negation
        '"(*budv* | будв* | херцег* | котор | бечичи) (инструмент | роутер | наушники | телефон | перфоратор) -iphone -услуги"',  # Full example
        '"(budv* | будв* | херцег* | котор | бечичи) кроссовки (43 | 44)"',  # Another example
    ]

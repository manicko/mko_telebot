import re

TOKEN_RE = re.compile(r'"(.*?)"|[-\w*]+|\||\(|\)')


def prepare_token(t):
    """Преобразует токен в regex с учетом * и строгих границ"""
    neg = t.startswith('-')
    word = t[1:] if neg else t

    if word.endswith('*'):
        regex_word = r'\b' + re.escape(word[:-1]) + r'\w*\b'
    else:
        regex_word = r'\b' + re.escape(word) + r'\b'

    return f'(?!.*{regex_word})' if neg else f'(?=.*{regex_word})'


def parse_tokens(tokens):
    pattern = '^'
    for t in tokens:
        if t == '|':
            pattern += '|'
        elif t == '(':
            pattern += '(?:'
        elif t == ')':
            pattern += ')'
        else:
            pattern += prepare_token(t)
    pattern += '.*$'
    return pattern


def search_match(text, query):
    tokens = [m.group(1) if m.group(1) else m.group(0) for m in TOKEN_RE.finditer(query.lower())]
    regex = parse_tokens(tokens)
    return re.search(regex, text.lower()) is not None


text1=' молоко -сахар'
text2='(кофе | чай) -сахар'
text3='("черный чай"|"зеленый чай") -молоко'
text4='cats dogs -parrots'
text5='"(cats | dogs) -parrots'

stext = 'молоки зелены чайи нет кофта,  есть dogs и  cats черный чай'

print(search_match(stext, text1))
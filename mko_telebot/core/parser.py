import re
from typing import List, Tuple, Union
from dataclasses import dataclass


@dataclass
class ASTNode:
    pass


@dataclass
class ExactMatch(ASTNode):
    value: str


@dataclass
class OrOperation(ASTNode):
    left: ASTNode
    right: ASTNode


@dataclass
class Sequence(ASTNode):
    elements: List[ASTNode]


@dataclass
class Wildcard(ASTNode):
    pattern: str


@dataclass
class Exclusion(ASTNode):
    child: ASTNode


class PatternParser:
    """Парсер паттернов с построением AST"""

    def __init__(self, query: str):
        self.query = query
        self.tokens = self._tokenize()
        self.token_pos = 0

    def _tokenize(self) -> List[Tuple[str, str]]:
        tokens = []
        i = 0
        q = self.query
        while i < len(q):
            ch = q[i]
            if ch == '(':
                tokens.append(('GROUP_START', '('))
                i += 1
            elif ch == ')':
                tokens.append(('GROUP_END', ')'))
                i += 1
            elif ch == '|':
                tokens.append(('OR', '|'))
                i += 1
            elif ch == '-':
                tokens.append(('EXCLUDE', '-'))
                i += 1
            elif ch.isspace():
                # пробел служит разделителем (AND), но токены пробела не нужны
                i += 1
            else:
                start = i
                while i < len(q) and q[i] not in '()|- ':
                    i += 1
                tokens.append(('TERM', q[start:i]))
        return tokens

    def _peek(self):
        return self.tokens[self.token_pos] if self.token_pos < len(self.tokens) else None

    def _consume(self, expected_type=None):
        tok = self._peek()
        if tok and (expected_type is None or tok[0] == expected_type):
            self.token_pos += 1
            return tok
        return None

    def parse(self) -> Tuple[List[ASTNode], List[ASTNode]]:
        inclusions: List[ASTNode] = []
        exclusions: List[ASTNode] = []

        while self._peek():
            tok = self._peek()
            if tok[0] == 'EXCLUDE':
                self._consume('EXCLUDE')
                excl = self._parse_or_expr()
                if excl:
                    exclusions.append(Exclusion(excl))
            else:
                inc = self._parse_or_expr()
                if inc:
                    inclusions.append(inc)
        return inclusions, exclusions

    # Grammar:
    # or_expr := and_expr ( 'OR' and_expr )*
    # and_expr := term ( term )*   # adjacency = Sequence (AND)
    # term := 'TERM' | '(' or_expr ')'

    def _parse_or_expr(self) -> ASTNode:
        left = self._parse_and_expr()
        while self._peek() and self._peek()[0] == 'OR':
            self._consume('OR')
            right = self._parse_and_expr()
            left = OrOperation(left, right)
        return left

    def _parse_and_expr(self) -> ASTNode:
        first = self._parse_term()
        elems = [first] if first is not None else []
        while True:
            tok = self._peek()
            if not tok or tok[0] in ('OR', 'GROUP_END', 'EXCLUDE'):
                break
            nxt = self._parse_term()
            if nxt is None:
                break
            elems.append(nxt)
        if len(elems) == 1:
            return elems[0]
        return Sequence(elems)

    def _parse_term(self) -> Union[ASTNode, None]:
        tok = self._peek()
        if not tok:
            return None
        if tok[0] == 'TERM':
            self._consume('TERM')
            val = tok[1]
            if '*' in val:
                return Wildcard(val)
            return ExactMatch(val)
        if tok[0] == 'GROUP_START':
            self._consume('GROUP_START')
            inner = self._parse_or_expr()
            if self._peek() and self._peek()[0] == 'GROUP_END':
                self._consume('GROUP_END')
            return inner
        # unexpected token: consume and ignore
        self._consume()
        return None


def ast_to_regex(node: ASTNode) -> str:
    """Построить regex для одиночного узла или OR-узла.
    ExactMatch -> \bword\b
    Wildcard  -> обработка '*' -> [^\\s]*
    OrOperation -> (?:left|right)
    Sequence обрабатывается отдельно (см. patterns_for_node).
    """
    if isinstance(node, ExactMatch):
        return rf'\b{re.escape(node.value)}\b'
    if isinstance(node, Wildcard):
        orig = node.pattern
        escaped = re.escape(orig)
        pattern = escaped.replace(r'\*', r'[^\s]*')
        if not orig.startswith('*'):
            pattern = r'\b' + pattern
        if not orig.endswith('*'):
            pattern = pattern + r'\b'
        return pattern
    if isinstance(node, OrOperation):
        left = ast_to_regex(node.left)
        right = ast_to_regex(node.right)
        return f'(?:{left}|{right})'
    if isinstance(node, Exclusion):
        return ast_to_regex(node.child)
    # Sequence should not come here for single-regex usage
    return ''


def patterns_for_node(node: ASTNode) -> List[str]:
    """
    Для заданного узла вернуть список regex-паттернов, каждый из которых
    обязан встретиться в тексте (unordered AND).
    - ExactMatch -> [\bword\b]
    - Wildcard -> [pattern]
    - OrOperation -> [ (?:a|b) ]  (один паттерн, одна из альтернатив должна встретиться)
    - Sequence -> flatten: собрать паттерны для каждого элемента (в любом порядке)
    - Exclusion -> вернуть паттерны из child (используется при проверке исключений)
    """
    if isinstance(node, ExactMatch):
        return [ast_to_regex(node)]
    if isinstance(node, Wildcard):
        return [ast_to_regex(node)]
    if isinstance(node, OrOperation):
        return [ast_to_regex(node)]
    if isinstance(node, Sequence):
        parts: List[str] = []
        for elem in node.elements:
            parts.extend(patterns_for_node(elem))
        return parts
    if isinstance(node, Exclusion):
        return patterns_for_node(node.child)
    return []


def search_match(text: str, query: str) -> bool:
    """
    Новая версия: порядок в Sequence не важен.
    Семантика:
      - пробел = логический AND (в любом порядке)
      - '|' = OR
      - '-' перед выражением = исключение (если найдено -> False)
      - скобки () для группировки
      - '*' внутри терма -> wildcard: '*' -> [^\\s]*, границы слова добавляются, если * не стоит слева/справа
    """
    if query is None:
        return False
    clean = query.strip().strip('"\'')
    if clean == '':
        return False

    try:
        parser = PatternParser(clean)
        inclusions, exclusions = parser.parse()

        # Сначала исключения: если любой exclusion совпадает -> False
        for excl in exclusions:
            excl_patterns = patterns_for_node(excl)
            for pat in excl_patterns:
                if pat and re.search(pat, text, flags=re.IGNORECASE | re.UNICODE):
                    return False

        # Затем включения: для каждого включения (выражения) — все его подшаблоны
        # должны встретиться где-то в тексте (в любом порядке).
        # Если inclusion — OrOperation, patterns_for_node вернёт один OR-паттерн,
        # т.е. достаточно найти любую альтернативу.
        for inc in inclusions:
            required = patterns_for_node(inc)
            if not required:
                # пустое включение считаем не совпавшим
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

        # Если были включения и все они прошли — True.
        # Если включений нет, но были исключения (и они не сработали) — True.
        return len(inclusions) > 0 or len(exclusions) > 0

    except Exception:
        return False

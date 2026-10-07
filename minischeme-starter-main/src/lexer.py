"""词法分析：程序文本 → 词（token）列表（spec §3）。

只做一件事：把字符流切成有类型的"零件"，不关心它们的组合关系
（嵌套结构交给 :mod:`parser`）。每个词都记录行列号，方便报错时定位。
"""

import re

from datamodel import Symbol
from errors import SchemeSyntaxError

# 词的类型（kind）
LPAREN = "("
RPAREN = ")"
QUOTE = "'"
NUMBER = "number"
BOOLEAN = "boolean"
STRING = "string"
SYMBOL = "symbol"

_INTEGER_RE = re.compile(r"[+-]?\d+$")
_FLOAT_RE = re.compile(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")

_DELIMITERS = "()'\";"
_WHITESPACE = " \t\r\n\f\v"


class Token:
    """一个词：类型、内容、以及它在源文件中的位置。"""

    __slots__ = ("kind", "value", "line", "column")

    def __init__(self, kind, value, line, column):
        self.kind = kind
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return "Token(%s, %r)" % (self.kind, self.value)


def tokenize(source):
    """把整段程序文本切成词列表。"""
    tokens = []
    position = 0
    line = 1
    column = 1
    length = len(source)

    while position < length:
        char = source[position]

        # 换行：只维护行列号
        if char == "\n":
            position += 1
            line += 1
            column = 1
            continue

        # 空白（零件之间的分隔）
        if char in _WHITESPACE:
            position += 1
            column += 1
            continue

        # 注释：`;` 到行尾全部忽略
        if char == ";":
            while position < length and source[position] != "\n":
                position += 1
                column += 1
            continue

        # 括号与引用简写：都是单字符词
        if char in (LPAREN, RPAREN, QUOTE):
            tokens.append(Token(char, char, line, column))
            position += 1
            column += 1
            continue

        # 字符串字面量
        if char == '"':
            text, position, line, column = _read_string(source, position, line, column)
            tokens.append(Token(STRING, text, line, column))
            continue

        # 其余情况：一个原子（数字 / 布尔 / 符号）
        start = position
        start_column = column
        while position < length and source[position] not in _DELIMITERS and source[position] not in _WHITESPACE:
            position += 1
            column += 1
        raw = source[start:position]
        tokens.append(Token(*_classify(raw, line, start_column)))
        continue

    return tokens


def _read_string(source, position, line, column):
    """读取以 ``"`` 开头的字符串，处理 ``\\n \\t \\" \\\\`` 四种转义。"""
    start_line, start_column = line, column
    position += 1  # 跳过左引号
    column += 1
    characters = []
    while True:
        if position >= len(source):
            raise SchemeSyntaxError(
                "第 %d 行第 %d 列的字符串没有闭合（缺少右引号）" % (start_line, start_column)
            )
        char = source[position]
        if char == '"':
            position += 1
            column += 1
            return "".join(characters), position, line, column
        if char == "\\":
            position += 1
            column += 1
            if position >= len(source):
                raise SchemeSyntaxError(
                    "第 %d 行第 %d 列的字符串以反斜杠结尾" % (start_line, start_column)
                )
            escaped = source[position]
            characters.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(escaped, escaped))
            position += 1
            column += 1
            continue
        if char == "\n":  # 字符串里允许直接换行
            line += 1
            column = 1
        else:
            column += 1
        characters.append(char)
        position += 1


def _classify(raw, line, column):
    """判断一个原子是布尔、整数、浮点还是符号。"""
    if raw == "#t":
        return BOOLEAN, True, line, column
    if raw == "#f":
        return BOOLEAN, False, line, column
    if _INTEGER_RE.match(raw):
        return NUMBER, int(raw), line, column
    if _FLOAT_RE.match(raw):
        return NUMBER, float(raw), line, column
    if raw.startswith("#"):
        raise SchemeSyntaxError("第 %d 行第 %d 列：无法识别的字面量 %s" % (line, column, raw))
    return SYMBOL, Symbol(raw), line, column

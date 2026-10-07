"""语法分析：词列表 → 表达式（嵌套的 Pair / NIL 结构）。

语法非常规整：原子直接成表达式；``'`` 展开成 ``(quote ...)``；
一对括号把里面的表达式串成点对链。列表在解析阶段就用点对表示，
所以 ``quote`` 得到的数据和 ``cons`` 造出的数据天然是同一种结构。
"""

from datamodel import Pair, Symbol, scheme_list
from errors import SchemeSyntaxError
from lexer import LPAREN, QUOTE, RPAREN, SYMBOL, tokenize


def parse(source):
    """文本 → 顶层表达式列表（词法 + 语法一步到位，便于入口调用）。"""
    return parse_tokens(tokenize(source))


def parse_tokens(tokens):
    """词列表 → 顶层表达式列表。"""
    expressions = []
    position = 0
    while position < len(tokens):
        expression, position = _parse_expression(tokens, position)
        expressions.append(expression)
    return expressions


def _parse_expression(tokens, position):
    """解析一个表达式，返回 ``(表达式, 下一个词的下标)``。"""
    if position >= len(tokens):
        raise SchemeSyntaxError("程序意外结束：缺少一个表达式")

    token = tokens[position]

    if token.kind == RPAREN:
        raise SchemeSyntaxError("第 %d 行第 %d 列有多余的右括号" % (token.line, token.column))

    if token.kind == LPAREN:
        items = []
        position += 1
        while True:
            if position >= len(tokens):
                raise SchemeSyntaxError(
                    "第 %d 行第 %d 列的左括号没有对应的右括号" % (token.line, token.column)
                )
            if tokens[position].kind == RPAREN:
                return scheme_list(*items), position + 1
            # 点对写法 `(1 . 2)`：点号把"链尾"单独写出来（spec §6）
            if _is_dot(tokens[position]):
                if not items:
                    raise SchemeSyntaxError(
                        "第 %d 行第 %d 列的点号前面必须至少有一个元素"
                        % (tokens[position].line, tokens[position].column)
                    )
                if position + 1 >= len(tokens) or tokens[position + 1].kind == RPAREN:
                    raise SchemeSyntaxError("点对写法 (a . b) 里点号后面必须有一个表达式")
                tail, position = _parse_expression(tokens, position + 1)
                if position >= len(tokens) or tokens[position].kind != RPAREN:
                    raise SchemeSyntaxError("点对写法 (a . b) 里点号后面只能有一个表达式")
                return _chain(items, tail), position + 1
            item, position = _parse_expression(tokens, position)
            items.append(item)

    if token.kind == QUOTE:
        # 'x 是 (quote x) 的简写（spec §4.1）
        quoted, position = _parse_expression(tokens, position + 1)
        return scheme_list(Symbol("quote"), quoted), position

    return token.value, position + 1


def _is_dot(token):
    """点对写法里的那个孤立的 ``.``。注意 ``.5`` 是数字，不会被误判。"""
    return token.kind == SYMBOL and token.value.name == "."


def _chain(items, tail):
    """把若干元素接成点对链，链尾是 ``tail``（真列表时 ``tail`` 就是 NIL）。"""
    result = tail
    for item in reversed(items):
        result = Pair(item, result)
    return result

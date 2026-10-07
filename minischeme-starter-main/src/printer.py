"""打印：把求值结果变成文本（spec §8）。

区分两种打印方式：

* :func:`to_write_string`  —— 顶层结果与嵌套元素的写法：字符串带引号，换行等
  转义成 ``\\n``、``\\t``。
* :func:`to_display_string` —— ``display`` 的写法：字符串原样输出（不带引号、
  转义字符还原成真实字符）。
"""

from datamodel import NIL, BuiltinProcedure, Closure, Pair, Symbol

_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
}


def to_write_string(value):
    """按"写入"规则渲染：``"a\\nb"`` -> ``"a\\nb"``（带引号与转义）。"""
    return _render(value, display=False)


def to_display_string(value):
    """按 ``display`` 规则渲染：字符串不带引号，转义还原为真实字符。"""
    return _render(value, display=True)


def _render(value, display):
    if value is True:
        return "#t"
    if value is False:
        return "#f"
    if value is NIL:
        return "()"
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, str):
        return value if display else _quote(value)
    if isinstance(value, bool):  # 理论上不会走到，留作兜底
        return "#t" if value else "#f"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, Pair):
        return _render_pair(value, display)
    if isinstance(value, (BuiltinProcedure, Closure)):
        return "#<procedure>"
    return str(value)  # None 等：正常不会被打印


def _number(value):
    """整数直接写；浮点用 repr，``0.5`` 才不会变成 ``.5`` 或 ``0.500000``。"""
    if isinstance(value, int):
        return str(value)
    return repr(value)


def _quote(text):
    return '"%s"' % "".join(_ESCAPES.get(char, char) for char in text)


def _render_pair(pair, display):
    """渲染点对链：``(1 2 3)`` 是真列表，``(1 . 2)`` 是点对。"""
    parts = []
    current = pair
    while isinstance(current, Pair):
        parts.append(_render(current.car, display))
        current = current.cdr
    if current is NIL:  # 真列表
        return "(%s)" % " ".join(parts)
    return "(%s . %s)" % (" ".join(parts), _render(current, display))

"""mini-Scheme 的数据模型：只描述"值长什么样"，不含任何求值逻辑。

设计要点：

* 列表统一用点对链表示（spec §6）。`quote` 出来的数据和 `cons`/`list`
  构造出来的数据因此是同一套结构，打印、比较都只有一套规则。
* :class:`Symbol` 故意**不继承** `str`。否则 ``(eq? 'a "a")`` 会因 Python 的
  字符串相等而误判为真（spec §11）。同名符号全局唯一，`eq?` 可以直接用
  `is` 比较。
* 空表 ``()`` 是全局唯一实例 :data:`NIL`，因此 ``(eq? '() '())`` 为真。
"""

from errors import SchemeError


class Symbol:
    """符号：变量名或操作符名，例如 ``foo``、``+``、``else``。"""

    __slots__ = ("name",)

    _interned = {}  # 名字 -> Symbol，保证同名符号是同一个对象

    def __new__(cls, name):
        existing = cls._interned.get(name)
        if existing is not None:
            return existing
        symbol = super().__new__(cls)
        symbol.name = name
        cls._interned[name] = symbol
        return symbol

    def __repr__(self):
        return self.name


class _Nil:
    """空表 ``()``，点对链的终点。"""

    __slots__ = ()

    def __repr__(self):
        return "()"


NIL = _Nil()


class Pair:
    """点对：``(1 2 3)`` 实际是 ``(1 . (2 . (3 . ())))``。"""

    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def __repr__(self):
        return "#<pair>"


class BuiltinProcedure:
    """内置过程（spec §5）：一个 Python 函数 + 它在语言里的名字。"""

    __slots__ = ("name", "func")

    def __init__(self, name, func):
        self.name = name
        self.func = func

    def __repr__(self):
        return "#<procedure %s>" % self.name


class Closure:
    """用户定义的函数：形参、函数体，以及**定义时**的环境（闭包的关键）。"""

    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params, body, env, name=None):
        self.params = params
        self.body = body
        self.env = env
        self.name = name

    def __repr__(self):
        return "#<procedure %s>" % (self.name or "lambda")


# --------------------------------------------------------------------------
# 值的小工具：类型判断与列表构造/拆解
# --------------------------------------------------------------------------

def is_number(value):
    """数字不包括布尔：Python 里 ``True`` 是 ``int`` 的子类，必须排除。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_true(value):
    """求值世界的真假判断：只有 ``#f`` 是假，``0``、``()``、``""`` 都是真。"""
    return value is not False


def is_procedure(value):
    return isinstance(value, (BuiltinProcedure, Closure))


def scheme_list(*items):
    """把 Python 列表打包成点对链，例如 ``scheme_list(1, 2)`` -> ``(1 2)``。"""
    result = NIL
    for item in reversed(items):
        result = Pair(item, result)
    return result


def pair_to_python_list(value, where="该表达式"):
    """把点对链拆成 Python 列表；不是真列表就报错（说明写法有问题）。"""
    items = []
    current = value
    while isinstance(current, Pair):
        items.append(current.car)
        current = current.cdr
    if current is not NIL:
        raise SchemeError("%s不是真正的列表（多余的点或缺少右括号）" % where)
    return items


def is_proper_list(value):
    """是否为真列表：``(list? (cons 1 2))`` -> ``#f``。"""
    current = value
    while isinstance(current, Pair):
        current = current.cdr
    return current is NIL

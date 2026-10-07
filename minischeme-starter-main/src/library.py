"""内置过程库：实现 spec §5 的全部标准函数，并装进初始环境。

每个内置过程都是一个"接收已求值实参列表、返回一个值"的 Python 函数，
参数在调用前已由求值器全部算好（应用序求值，spec §9）。
"""

import math
import operator
import sys

from datamodel import (
    NIL,
    BuiltinProcedure,
    Pair,
    Symbol,
    is_number,
    is_proper_list,
    is_procedure,
    pair_to_python_list,
    scheme_list,
)
from errors import SchemeError
from printer import to_display_string, to_write_string


def install_builtins(environment):
    """把所有内置过程绑定到给定环境（入口在启动时调用一次）。"""
    for name, function in _BUILTINS.items():
        environment.define(Symbol(name), BuiltinProcedure(name, function))


# --------------------------------------------------------------------------
# 参数校验小工具：统一错误提示，也避免重复代码
# --------------------------------------------------------------------------

def _require_count(name, args, minimum, maximum=None):
    count = len(args)
    if count < minimum or (maximum is not None and count > maximum):
        if maximum is None:
            expected = "至少 %d" % minimum
        elif minimum == maximum:
            expected = "%d" % minimum
        else:
            expected = "%d ~ %d" % (minimum, maximum)
        raise SchemeError("%s 需要 %s 个参数，实际得到 %d 个" % (name, expected, count))


def _require_numbers(name, args):
    for value in args:
        if not is_number(value):
            raise SchemeError("%s 的参数必须是数字，得到：%s" % (name, _show(value)))


def _show(value):
    """错误信息里展示一个值，用的是"写入"写法（字符串带引号）。"""
    return to_write_string(value)


# --------------------------------------------------------------------------
# 算术
# --------------------------------------------------------------------------

def _truncating_divide(dividend, divisor):
    """整数相除取整数商，负数向零截断：``(/ -7 2)`` -> ``-3``（spec §5）。"""
    if dividend == 0:
        return 0
    quotient = abs(dividend) // abs(divisor)
    return -quotient if (dividend < 0) != (divisor < 0) else quotient


def _add(args):
    _require_numbers("+", args)
    return sum(args)


def _subtract(args):
    _require_count("-", args, 1)
    _require_numbers("-", args)
    if len(args) == 1:
        return -args[0]
    result = args[0]
    for value in args[1:]:
        result -= value
    return result


def _multiply(args):
    _require_numbers("*", args)
    result = 1
    for value in args:
        result *= value
    return result


def _divide(args):
    _require_count("/", args, 1)
    _require_numbers("/", args)
    if len(args) == 1:
        if args[0] == 0:
            raise SchemeError("除数不能为 0")
        return 1 / args[0]  # 单参数取倒数，结果为浮点：`(/ 2)` -> 0.5
    result = args[0]
    for divisor in args[1:]:
        if divisor == 0:
            raise SchemeError("除数不能为 0")
        if isinstance(result, int) and isinstance(divisor, int):
            result = _truncating_divide(result, divisor)
        else:
            result = result / divisor
    return result


def _modulo(args):
    _require_count("modulo", args, 2, 2)
    _require_numbers("modulo", args)
    dividend, divisor = args
    if divisor == 0:
        raise SchemeError("modulo 的第二个参数不能为 0")
    if isinstance(dividend, int) and isinstance(divisor, int):
        return dividend % divisor  # Python 的 % 与 Scheme 的 modulo 符号规则一致
    return math.fmod(dividend, divisor)


def _quotient(args):
    _require_count("quotient", args, 1)
    _require_numbers("quotient", args)
    result = args[0]
    for divisor in args[1:]:
        if divisor == 0:
            raise SchemeError("quotient 的第二个参数不能为 0")
        if isinstance(result, int) and isinstance(divisor, int):
            result = _truncating_divide(result, divisor)
        else:
            result = math.trunc(result / divisor)
    return result


def _expt(args):
    _require_count("expt", args, 2, 2)
    _require_numbers("expt", args)
    return args[0] ** args[1]  # 整数底与负指数时 Python 自动给出浮点：0.5


def _abs(args):
    _require_count("abs", args, 1, 1)
    _require_numbers("abs", args)
    return abs(args[0])


# --------------------------------------------------------------------------
# 比较（链式）与布尔
# --------------------------------------------------------------------------

def _make_comparison(name, compare):
    """生成链式比较过程：相邻两个都成立才算真，``(< 2 3 4)`` -> ``#t``。"""

    def builtin(args):
        _require_count(name, args, 1)
        for left, right in zip(args, args[1:]):
            if not _compare_pair(name, compare, left, right):
                return False
        return True

    return builtin


def _compare_pair(name, compare, left, right):
    """数字按数值比较，符号按名字比较（spec §5 注明比较支持符号）。"""
    if is_number(left) and is_number(right):
        return compare(left, right)
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return compare(left.name, right.name)
    raise SchemeError(
        "%s 只能比较数字或符号，得到：%s 与 %s" % (name, _show(left), _show(right))
    )


def _not(args):
    _require_count("not", args, 1, 1)
    return args[0] is False


# --------------------------------------------------------------------------
# 列表（点对链）
# --------------------------------------------------------------------------

def _cons(args):
    _require_count("cons", args, 2, 2)
    return Pair(args[0], args[1])


def _car(args):
    _require_count("car", args, 1, 1)
    if not isinstance(args[0], Pair):
        raise SchemeError("car 需要点对，得到：%s" % _show(args[0]))
    return args[0].car


def _cdr(args):
    _require_count("cdr", args, 1, 1)
    if not isinstance(args[0], Pair):
        raise SchemeError("cdr 需要点对，得到：%s" % _show(args[0]))
    return args[0].cdr


def _list(args):
    return scheme_list(*args)


def _length(args):
    _require_count("length", args, 1, 1)
    if not is_proper_list(args[0]):
        raise SchemeError("length 需要真列表，得到：%s" % _show(args[0]))
    count = 0
    current = args[0]
    while isinstance(current, Pair):
        count += 1
        current = current.cdr
    return count


def _append(args):
    if not args:
        return NIL
    result = args[-1]  # 最后一项可以是任意值，其余必须是列表
    for value in reversed(args[:-1]):
        for item in reversed(pair_to_python_list(value, "append 的参数")):
            result = Pair(item, result)
    return result


def _null_p(args):
    _require_count("null?", args, 1, 1)
    return args[0] is NIL


def _pair_p(args):
    _require_count("pair?", args, 1, 1)
    return isinstance(args[0], Pair)


def _list_p(args):
    _require_count("list?", args, 1, 1)
    return is_proper_list(args[0])


# --------------------------------------------------------------------------
# 谓词
# --------------------------------------------------------------------------

def _make_type_predicate(name, test):
    def builtin(args):
        _require_count(name, args, 1, 1)
        return test(args[0])

    return builtin


def _number_p(args):
    _require_count("number?", args, 1, 1)
    return is_number(args[0])


def _make_numeric_predicate(name, test):
    def builtin(args):
        _require_count(name, args, 1, 1)
        _require_numbers(name, args)
        return bool(test(args[0]))

    return builtin


def _eq(args):
    """eq?：符号、数字、布尔按值比较；复合数据按同一性（spec §5）。"""
    _require_count("eq?", args, 2, 2)
    return _eq_values(args[0], args[1])


def _eq_values(left, right):
    if left is right:
        return True
    if isinstance(left, bool) or isinstance(right, bool):
        return False  # `#t` 与 `1` 不是同一个东西
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    if isinstance(left, str) and isinstance(right, str):
        return left == right  # 字符串是简单数据，按值比较
    return False  # 点对等复合数据按同一性：两个内容相同的列表也不 eq?


def _equal(args):
    """equal?：结构相等，逐层比较；先比类型再比值。"""
    _require_count("equal?", args, 2, 2)
    return _equal_values(args[0], args[1])


def _equal_values(left, right):
    if left is right:
        return True
    if isinstance(left, bool) or isinstance(right, bool):
        return False  # `(equal? #t 1)` -> #f
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name  # `(equal? 'a "a")` -> #f
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    if isinstance(left, Pair) and isinstance(right, Pair):
        return _equal_values(left.car, right.car) and _equal_values(left.cdr, right.cdr)
    return False


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

def _display(args):
    _require_count("display", args, 1, 1)
    sys.stdout.write(to_display_string(args[0]))
    return None  # None 不打印，所以 display 本身不产生结果行


def _newline(args):
    _require_count("newline", args, 0, 0)
    sys.stdout.write("\n")
    return None


# --------------------------------------------------------------------------
# 名字 → 过程 的注册表（对照 spec §5 的表格，一眼可查）
# --------------------------------------------------------------------------

_BUILTINS = {
    # 算术
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "modulo": _modulo,
    "quotient": _quotient,
    "expt": _expt,
    "abs": _abs,
    # 比较与布尔
    "=": _make_comparison("=", operator.eq),
    "<": _make_comparison("<", operator.lt),
    ">": _make_comparison(">", operator.gt),
    "<=": _make_comparison("<=", operator.le),
    ">=": _make_comparison(">=", operator.ge),
    "not": _not,
    # 列表
    "cons": _cons,
    "car": _car,
    "cdr": _cdr,
    "list": _list,
    "length": _length,
    "append": _append,
    "null?": _null_p,
    "pair?": _pair_p,
    "list?": _list_p,
    # 谓词
    "number?": _number_p,
    "boolean?": _make_type_predicate("boolean?", lambda value: isinstance(value, bool)),
    "symbol?": _make_type_predicate("symbol?", lambda value: isinstance(value, Symbol)),
    "string?": _make_type_predicate("string?", lambda value: isinstance(value, str)),
    "procedure?": _make_type_predicate("procedure?", is_procedure),
    "zero?": _make_numeric_predicate("zero?", lambda value: value == 0),
    "even?": _make_numeric_predicate("even?", lambda value: value % 2 == 0),
    "odd?": _make_numeric_predicate("odd?", lambda value: value % 2 != 0),
    "eq?": _eq,
    "equal?": _equal,
    # 输出
    "display": _display,
    "newline": _newline,
}

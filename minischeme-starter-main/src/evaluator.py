"""求值器：解释器的心脏——``evaluate`` 与 ``apply_procedure`` 互相递归（README §4）。

* ``evaluate(表达式, 环境)``：符号去环境里查；数字/布尔/字符串原样返回；
  点对要么是特殊形式（按 spec §4 各自的求值顺序），要么是函数调用
  （先求值操作符和全部实参，再交给 ``apply_procedure``）。
* ``apply_procedure(过程, 实参)``：内置过程直接调用；闭包则新建一层环境，
  把实参绑到形参上（外层指向函数**定义时**的环境），再回去求值函数体。
"""

from datamodel import (
    BuiltinProcedure,
    Closure,
    NIL,
    Pair,
    Symbol,
    is_true,
    pair_to_python_list,
)
from environment import Environment
from errors import SchemeError, SchemeSyntaxError
from printer import to_write_string


def evaluate(expression, environment):
    """求值一个表达式，返回一个值。"""
    if isinstance(expression, Symbol):
        return environment.lookup(expression)

    if isinstance(expression, Pair):
        return _evaluate_pair(expression, environment)

    if expression is NIL:
        raise SchemeError("空表 () 不是合法的表达式（要表示空表请写 '()）")

    return expression  # 数字、布尔、字符串是自求值的


def _evaluate_pair(expression, environment):
    """点对表达式：先看是不是特殊形式，否则按函数调用处理。"""
    operator = expression.car
    operands = pair_to_python_list(expression.cdr, "函数调用的实参")

    if isinstance(operator, Symbol):
        special_form = _SPECIAL_FORMS.get(operator.name)
        if special_form is not None:
            return special_form(operands, environment)

    procedure = evaluate(operator, environment)
    arguments = [evaluate(operand, environment) for operand in operands]
    return apply_procedure(procedure, arguments)


def apply_procedure(procedure, arguments):
    """调用一个过程。内置过程直接调用；闭包建新环境后回到 evaluate。"""
    if not isinstance(procedure, (BuiltinProcedure, Closure)):
        raise SchemeError("%s 不是过程，无法调用" % to_write_string(procedure))

    if isinstance(procedure, Closure):
        if len(arguments) != len(procedure.params):
            raise SchemeError(
                "%s 需要 %d 个参数，实际得到 %d 个"
                % (_procedure_name(procedure), len(procedure.params), len(arguments))
            )
        local = Environment(procedure.env)
        for parameter, argument in zip(procedure.params, arguments):
            local.define(parameter, argument)
        return _evaluate_sequence(procedure.body, local)

    return procedure.func(arguments)  # 实参已求值，直接交给 Python 函数


def _procedure_name(procedure):
    return procedure.name or "该函数"


# --------------------------------------------------------------------------
# 特殊形式（spec §4）：每个函数接收"未求值的操作数列表"和当前环境
# --------------------------------------------------------------------------

def _check_operand_count(name, operands, minimum, maximum=None):
    count = len(operands)
    if count < minimum or (maximum is not None and count > maximum):
        if maximum is None:
            expected = "至少 %d" % minimum
        elif minimum == maximum:
            expected = "%d" % minimum
        else:
            expected = "%d ~ %d" % (minimum, maximum)
        raise SchemeSyntaxError("%s 需要 %s 个部分，实际得到 %d 个" % (name, expected, count))


def _evaluate_sequence(expressions, environment):
    """按 begin 语义依次求值，返回最后一个结果（空则返回 None）。"""
    result = None
    for expression in expressions:
        result = evaluate(expression, environment)
    return result


def _eval_quote(operands, environment):
    """(quote 数据)：原样返回，不求值（spec §4.1）。"""
    _check_operand_count("quote", operands, 1, 1)
    return operands[0]


def _eval_if(operands, environment):
    """(if 测试 真分支 假分支?)：只求值一个分支（spec §4.2）。"""
    _check_operand_count("if", operands, 2, 3)
    if is_true(evaluate(operands[0], environment)):
        return evaluate(operands[1], environment)
    if len(operands) == 3:
        return evaluate(operands[2], environment)
    return None  # 省略假分支且测试为假时没有值，不打印


def _eval_cond(operands, environment):
    """(cond 子句...)：从上到下找第一个成立的测试（spec §4.3）。"""
    for clause_expression in operands:
        clause = pair_to_python_list(clause_expression, "cond 的子句")
        if not clause:
            raise SchemeSyntaxError("cond 的子句不能为空")
        test_expression, body = clause[0], clause[1:]

        if isinstance(test_expression, Symbol) and test_expression.name == "else":
            return _evaluate_sequence(body, environment)

        value = evaluate(test_expression, environment)
        if is_true(value):
            if not body:
                return value  # 子句里没有表达式时，返回测试值本身
            return _evaluate_sequence(body, environment)

    return None  # 全部不匹配


def _eval_and(operands, environment):
    """(and ...)：遇到 #f 立刻返回，全部为真返回最后一个值（spec §4.4）。"""
    result = True
    for operand in operands:
        result = evaluate(operand, environment)
        if result is False:
            return False
    return result


def _eval_or(operands, environment):
    """(or ...)：遇到第一个不为 #f 的值立刻返回（spec §4.4）。"""
    for operand in operands:
        result = evaluate(operand, environment)
        if result is not False:
            return result
    return False


def _eval_define(operands, environment):
    """(define 名 表达式) 与 (define (函数名 参数...) 体...)（spec §4.5）。"""
    _check_operand_count("define", operands, 2)
    target = operands[0]

    if isinstance(target, Symbol):  # 定义变量
        _check_operand_count("define", operands, 2, 2)
        value = evaluate(operands[1], environment)
        environment.define(target, value)
        return target  # define 的结果是被定义的符号名

    # 定义函数的简写：等价于 (define 名 (lambda (参数...) 体...))
    signature = pair_to_python_list(target, "define 的函数签名")
    if not signature or not isinstance(signature[0], Symbol):
        raise SchemeSyntaxError("define 的写法应是 (define 名 表达式) 或 (define (函数名 参数...) 体...)")
    name = signature[0]
    environment.define(name, _make_closure(signature[1:], operands[1:], environment, name))
    return name


def _eval_lambda(operands, environment):
    """(lambda (参数...) 体...)：产生闭包，函数体此时不求值（spec §4.6）。"""
    _check_operand_count("lambda", operands, 2)
    parameters = pair_to_python_list(operands[0], "lambda 的参数表")
    return _make_closure(parameters, operands[1:], environment, None)


def _make_closure(parameters, body, environment, name):
    """校验形参表并造出闭包（记住定义时的环境）。"""
    seen = set()
    for parameter in parameters:
        if not isinstance(parameter, Symbol):
            raise SchemeSyntaxError("函数参数必须是符号，得到：%s" % to_write_string(parameter))
        if parameter.name in seen:
            raise SchemeSyntaxError("函数参数名重复：%s" % parameter.name)
        seen.add(parameter.name)
    if not body:
        raise SchemeSyntaxError("函数定义缺少函数体")
    return Closure(parameters, body, environment, name)


def _eval_let(operands, environment):
    """(let ((名 表达式)...) 体...)：并行绑定（spec §4.7）。"""
    _check_operand_count("let", operands, 2)
    binding_expressions = pair_to_python_list(operands[0], "let 的绑定表")

    local = Environment(environment)
    evaluated = []
    # 关键：所有绑定表达式都在**外层环境**求值（绑定之间互不可见），最后统一绑定
    for binding_expression in binding_expressions:
        binding = pair_to_python_list(binding_expression, "let 的绑定")
        if len(binding) != 2 or not isinstance(binding[0], Symbol):
            raise SchemeSyntaxError("let 的每个绑定都要写成 (名 表达式)")
        evaluated.append((binding[0], evaluate(binding[1], environment)))

    for name, value in evaluated:
        local.define(name, value)
    return _evaluate_sequence(operands[1:], local)


def _eval_begin(operands, environment):
    """(begin e1 e2 ...)：依次求值，返回最后一个（spec §4.8）。"""
    return _evaluate_sequence(operands, environment)


def _eval_else(operands, environment):
    raise SchemeSyntaxError("else 只能出现在 cond 的子句里")


_SPECIAL_FORMS = {
    "quote": _eval_quote,
    "if": _eval_if,
    "cond": _eval_cond,
    "and": _eval_and,
    "or": _eval_or,
    "define": _eval_define,
    "lambda": _eval_lambda,
    "let": _eval_let,
    "begin": _eval_begin,
    "else": _eval_else,
}

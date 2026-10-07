"""解释器向外抛出的错误类型。

所有"语言层面"的失败都收敛到 :class:`SchemeError`：入口只需捕获它一次，
就能把错误整理成一行提示，而不是把 Python 的 traceback 泄漏给学生。
"""


class SchemeError(Exception):
    """解释器运行期的语言错误：类型不符、参数个数不对、未定义的符号等。"""


class SchemeSyntaxError(SchemeError):
    """词法/语法错误（括号不配对、字符串没闭合、特殊形式写错等）。"""
